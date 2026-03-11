from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    ApprovalEntry,
    ConfigGetResult,
    ConfigRedaction,
    DiagnosticEntry,
    MemoryInspectEntry,
    MemoryInspectParams,
    MemoryInspectResult,
    PROTOCOL_VERSION,
    RuntimeHealthResult,
    TaskApprovalsListParams,
    TaskApprovalsListResult,
    TaskArtifactsListParams,
    TaskArtifactsListResult,
    TaskApproveParams,
    TaskApproveResult,
    TaskCreateParams,
    TaskCreateResult,
    TaskDiagnosticsListParams,
    TaskDiagnosticsListResult,
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
    config_sources: list[str] | None = None

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

    def task_approvals_list(self, params: dict) -> TaskApprovalsListResult:
        request = TaskApprovalsListParams.from_dict(params)
        approvals = self.durable_services.approval_store.list_for_task(
            request.task_id,
            request.run_id,
        )
        entries = [
            ApprovalEntry(
                approval_id=approval.approval_id,
                task_id=approval.task_id,
                run_id=approval.run_id,
                status=approval.status,
                type=approval.type,
                scope=dict(approval.scope),
                scope_summary=_scope_summary(approval.scope),
                description=approval.description,
                created_at=approval.created_at,
                decision=approval.decision,
                decided_at=approval.decided_at,
            )
            for approval in approvals
        ]
        return TaskApprovalsListResult(approvals=entries, count=len(entries))

    def task_diagnostics_list(self, params: dict) -> TaskDiagnosticsListResult:
        request = TaskDiagnosticsListParams.from_dict(params)
        diagnostics = self.durable_services.diagnostic_store.list_diagnostics(
            request.task_id,
            request.run_id,
        )
        return TaskDiagnosticsListResult(
            diagnostics=[
                DiagnosticEntry(
                    diagnostic_id=diagnostic.diagnostic_id,
                    task_id=diagnostic.task_id,
                    run_id=diagnostic.run_id,
                    kind=diagnostic.kind,
                    message=diagnostic.message,
                    created_at=diagnostic.created_at,
                    details=dict(diagnostic.details),
                )
                for diagnostic in diagnostics
            ],
            count=len(diagnostics),
        )

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

    def config_get(self) -> ConfigGetResult:
        redactions: list[ConfigRedaction] = []
        resolved_subagents = {
            resolved.asset_bundle.definition.role_id: {
                "role_id": resolved.asset_bundle.definition.role_id,
                "model_profile": resolved.asset_bundle.definition.model_profile,
                "resolved_model": {
                    "provider": resolved.model_route.provider,
                    "model": resolved.model_route.model,
                    "profile_name": resolved.model_route.profile_name,
                    "source": resolved.model_route.source,
                },
                "tool_bindings": [binding.tool_id for binding in resolved.tool_bindings],
                "skills": [skill.skill_id for skill in resolved.skills],
            }
            for resolved in self.task_runner.resolved_subagents
        }
        effective_config = _redact_config(
            {
                "runtime": {
                    "name": self.config.runtime.name,
                    "log_level": self.config.runtime.log_level,
                },
                "identity": {"path": self.config.identity_path},
                "transport": {"mode": self.config.transport.mode},
                "models": {
                    "default": {
                        "provider": self.config.default_model.provider,
                        "model": self.config.default_model.model,
                    },
                    "subagents": {
                        role: {"provider": model.provider, "model": model.model}
                        for role, model in self.config.subagent_model_overrides.items()
                    },
                    "resolved": {
                        "primary": {
                            "provider": self.config.default_model.provider,
                            "model": self.config.default_model.model,
                            "profile_name": "default",
                            "source": "default_model",
                        },
                        "subagents": {
                            role: definition["resolved_model"]
                            for role, definition in resolved_subagents.items()
                        },
                    },
                },
                "persistence": {
                    "root_path": self.config.persistence.root_path,
                    "metadata_backend": self.config.persistence.metadata_backend,
                    "event_backend": self.config.persistence.event_backend,
                    "diagnostic_backend": self.config.persistence.diagnostic_backend,
                },
                "subagents": resolved_subagents,
                "policy": dict(self.config.policy),
            },
            redactions,
        )
        return ConfigGetResult(
            effective_config=effective_config,
            loaded_profiles=[],
            config_sources=list(self.config_sources or [self.config.identity_path]),
            redactions=redactions,
        )

    def _select_memory_entries(self, request: MemoryInspectParams) -> list[MemoryRecord]:
        store = self.durable_services.memory_store
        if request.scope is None:
            entries = list(
                store.list_memory(scope=MEMORY_SCOPE_PROJECT, namespace=request.namespace)
            )
            if request.task_id is not None:
                entries.extend(
                    entry
                    for entry in store.list_memory(
                        scope=MEMORY_SCOPE_RUN_STATE,
                        namespace=request.namespace,
                    )
                    if _matches_memory_context(entry, request.task_id, request.run_id)
                )
            return sorted(entries, key=lambda entry: (entry.created_at, entry.memory_id))

        if request.scope == MEMORY_SCOPE_PROJECT:
            return store.list_memory(scope=MEMORY_SCOPE_PROJECT, namespace=request.namespace)
        if request.scope == MEMORY_SCOPE_IDENTITY:
            return store.list_memory(scope=MEMORY_SCOPE_IDENTITY, namespace=request.namespace)
        if request.scope == MEMORY_SCOPE_RUN_STATE:
            entries = store.list_memory(scope=MEMORY_SCOPE_RUN_STATE, namespace=request.namespace)
            if request.task_id is None:
                return entries
            return [
                entry
                for entry in entries
                if _matches_memory_context(entry, request.task_id, request.run_id)
            ]
        if request.scope == MEMORY_SCOPE_SCRATCH:
            entries = store.list_memory(scope=MEMORY_SCOPE_SCRATCH, namespace=request.namespace)
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


def _scope_summary(scope: dict[str, Any]) -> str:
    if "boundary_key" in scope:
        return str(scope["boundary_key"])
    if "path_scope" in scope:
        return str(scope["path_scope"])
    if "memory_scope" in scope:
        return f"memory:{scope['memory_scope']}"
    if not scope:
        return "unspecified"
    return ", ".join(f"{key}={value}" for key, value in sorted(scope.items()))


def _redact_config(
    value: Any,
    redactions: list[ConfigRedaction],
    *,
    path: str = "",
) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact_config(
                child,
                redactions,
                path=f"{path}.{key}" if path else str(key),
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [
            _redact_config(child, redactions, path=f"{path}[{index}]")
            for index, child in enumerate(value)
        ]
    if _is_sensitive_path(path):
        redactions.append(ConfigRedaction(path=path, reason="sensitive-key"))
        return "***REDACTED***"
    return value


def _is_sensitive_path(path: str) -> bool:
    lowered = path.lower()
    return any(token in lowered for token in ("secret", "token", "password", "api_key"))
