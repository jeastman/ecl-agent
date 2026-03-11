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
    PROTOCOL_VERSION,
    RuntimeHealthResult,
    TaskArtifactsListParams,
    TaskArtifactsListResult,
    TaskCreateParams,
    TaskCreateResult,
    TaskGetParams,
    TaskGetResult,
    TaskResumeParams,
    TaskResumeResult,
    TaskLogsStreamParams,
    TaskLogsStreamResult,
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
