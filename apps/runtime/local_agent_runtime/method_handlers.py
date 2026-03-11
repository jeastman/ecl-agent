from __future__ import annotations

from dataclasses import dataclass

from apps.runtime.local_agent_runtime.artifact_store import ArtifactStore
from apps.runtime.local_agent_runtime.durable_services import DurableRuntimeServices
from apps.runtime.local_agent_runtime.event_bus import EventBus
from apps.runtime.local_agent_runtime.recovery_service import persisted_event_to_runtime_event
from apps.runtime.local_agent_runtime.resume_service import ResumeService
from apps.runtime.local_agent_runtime.run_state_store import RunStateStore
from apps.runtime.local_agent_runtime.task_runner import TaskRunner
from packages.config.local_agent_config.models import RuntimeConfig
from packages.identity.local_agent_identity.models import IdentityBundle
from packages.protocol.local_agent_protocol.models import (
    MemoryInspectEntry,
    MemoryInspectParams,
    MemoryInspectResult,
    PROTOCOL_VERSION,
    RuntimeHealthResult,
    TaskArtifactsListParams,
    TaskArtifactsListResult,
    TaskApproveParams,
    TaskApproveResult,
    TaskCreateParams,
    TaskCreateResult,
    TaskGetParams,
    TaskGetResult,
    TaskResumeParams,
    TaskResumeResult,
    TaskLogsStreamParams,
    TaskLogsStreamResult,
)
from services.memory_service.local_agent_memory_service.memory_models import MemoryRecord
from services.memory_service.local_agent_memory_service.memory_promotion import (
    MEMORY_SCOPE_IDENTITY,
    MEMORY_SCOPE_PROJECT,
    MEMORY_SCOPE_RUN_STATE,
    MEMORY_SCOPE_SCRATCH,
)


@dataclass(slots=True)
class MethodHandlers:
    config: RuntimeConfig
    identity: IdentityBundle
    run_state_store: RunStateStore
    event_bus: EventBus
    artifact_store: ArtifactStore
    task_runner: TaskRunner
    durable_services: DurableRuntimeServices
    resume_service: ResumeService

    def runtime_health(self, correlation_id: str | None) -> RuntimeHealthResult:
        return RuntimeHealthResult(
            protocol_version=PROTOCOL_VERSION,
            runtime_name=self.config.runtime.name,
            runtime_version="0.1.0",
            status="ok",
            transport=self.config.transport.mode,
            correlation_id=correlation_id,
            identity={
                "path": self.identity.source_path,
                "version": self.identity.version,
                "sha256": self.identity.sha256,
            },
        )

    def task_create(self, params: dict, correlation_id: str | None) -> TaskCreateResult:
        request = TaskCreateParams.from_dict(params).task
        task_id, run_id, accepted_at = self.task_runner.start_run(
            correlation_id=correlation_id,
            objective=request.objective,
            workspace_roots=request.workspace_roots,
            identity_bundle_text=self.identity.content,
            allowed_capabilities=request.allowed_capabilities,
            metadata=request.metadata,
            constraints=request.constraints,
            success_criteria=request.success_criteria,
        )
        return TaskCreateResult(
            task_id=task_id,
            run_id=run_id,
            status="accepted",
            accepted_at=accepted_at,
        )

    def task_get(self, params: dict) -> TaskGetResult:
        request = TaskGetParams.from_dict(params)
        return TaskGetResult(
            task=self.task_runner.get_task_snapshot(request.task_id, request.run_id)
        )

    def task_approve(self, params: dict) -> TaskApproveResult:
        request = TaskApproveParams.from_dict(params)
        approval_id, accepted, status, snapshot = self.task_runner.approve(
            request.task_id,
            request.approval.approval_id,
            request.approval.decision,
            run_id=request.run_id,
            identity_bundle_text=self.identity.content,
        )
        return TaskApproveResult(
            approval_id=approval_id,
            accepted=accepted,
            status=status,
            task=snapshot,
        )

    def task_resume(self, params: dict) -> TaskResumeResult:
        request = TaskResumeParams.from_dict(params)
        return TaskResumeResult(task=self.resume_service.resume(request.task_id, request.run_id))

    def task_artifacts_list(self, params: dict) -> TaskArtifactsListResult:
        request = TaskArtifactsListParams.from_dict(params)
        return TaskArtifactsListResult(
            artifacts=self.task_runner.list_artifacts(
                request.task_id,
                request.run_id,
                persistence_class=request.persistence_class,
                content_type_prefix=request.content_type_prefix,
            )
        )

    def task_logs_stream(self, params: dict) -> tuple[TaskLogsStreamResult, list]:
        request = TaskLogsStreamParams.from_dict(params)
        state = self.run_state_store.get(request.task_id, request.run_id)
        history = []
        if request.include_history:
            history = [
                persisted_event_to_runtime_event(record)
                for record in self.durable_services.event_store.get_events(
                    task_id=request.task_id,
                    run_id=state.run_id,
                    from_event_id=request.from_event_id,
                )
            ]
        return (
            TaskLogsStreamResult(
                task_id=request.task_id,
                run_id=state.run_id,
                stream_open=True,
            ),
            history,
        )

    def memory_inspect(self, params: dict) -> MemoryInspectResult:
        request = MemoryInspectParams.from_dict(params)
        entries = self._select_memory_entries(request)
        return MemoryInspectResult(
            entries=[_memory_record_to_entry(entry) for entry in entries],
            scope=request.scope or "default",
            count=len(entries),
        )

    def _select_memory_entries(self, request: MemoryInspectParams) -> list[MemoryRecord]:
        store = self.durable_services.memory_store
        if request.scope is None:
            entries = list(store.list_memory(scope=MEMORY_SCOPE_PROJECT))
            if request.task_id is not None:
                entries.extend(
                    entry
                    for entry in store.list_memory(scope=MEMORY_SCOPE_RUN_STATE)
                    if _matches_memory_context(entry, request.task_id, request.run_id)
                )
            return sorted(entries, key=lambda entry: (entry.created_at, entry.memory_id))

        if request.scope == MEMORY_SCOPE_PROJECT:
            return store.list_memory(scope=MEMORY_SCOPE_PROJECT)
        if request.scope == MEMORY_SCOPE_IDENTITY:
            return store.list_memory(scope=MEMORY_SCOPE_IDENTITY)
        if request.scope == MEMORY_SCOPE_RUN_STATE:
            entries = store.list_memory(scope=MEMORY_SCOPE_RUN_STATE)
            if request.task_id is None:
                return entries
            return [
                entry
                for entry in entries
                if _matches_memory_context(entry, request.task_id, request.run_id)
            ]
        if request.scope == MEMORY_SCOPE_SCRATCH:
            entries = store.list_memory(scope=MEMORY_SCOPE_SCRATCH)
            if request.task_id is None:
                return entries
            return [
                entry
                for entry in entries
                if _matches_memory_context(entry, request.task_id, request.run_id)
            ]
        raise ValueError(
            "memory.inspect scope must be one of project, identity, run_state, scratch"
        )


def _memory_record_to_entry(record: MemoryRecord) -> MemoryInspectEntry:
    return MemoryInspectEntry(
        memory_id=record.memory_id,
        scope=record.scope,
        namespace=record.namespace,
        content=record.content,
        summary=record.summary,
        provenance=dict(record.provenance),
        created_at=record.created_at,
        updated_at=record.updated_at,
        source_run=record.source_run,
        confidence=record.confidence,
    )


def _matches_memory_context(record: MemoryRecord, task_id: str, run_id: str | None) -> bool:
    provenance_task_id = record.provenance.get("task_id")
    provenance_run_id = record.provenance.get("run_id")
    task_matches = provenance_task_id == task_id if provenance_task_id is not None else True
    if not task_matches:
        return False
    if run_id is None:
        return True
    return record.source_run == run_id or provenance_run_id == run_id
