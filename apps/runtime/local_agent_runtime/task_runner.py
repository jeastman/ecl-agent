from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from apps.runtime.local_agent_runtime.artifact_store import ArtifactStore
from apps.runtime.local_agent_runtime.durable_services import DurableRuntimeServices
from apps.runtime.local_agent_runtime.event_bus import EventBus
from apps.runtime.local_agent_runtime.run_state_store import RunStateStore
from packages.protocol.local_agent_protocol.models import (
    EventEnvelope,
    EventSource,
    EventSourceKind,
    RuntimeEvent,
    TaskSnapshot,
    utc_now_timestamp,
)
from packages.task_model.local_agent_task_model.ids import new_event_id, new_run_id, new_task_id
from packages.task_model.local_agent_task_model.models import (
    EventType,
    FailureInfo,
    RunState,
    TaskStatus,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.checkpoint_adapter import (
    CheckpointController,
    LangGraphCheckpointAdapter,
)
from services.observability_service.local_agent_observability_service.observability_models import (
    RunMetricsRecord,
)
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    ExecutionSandbox,
    LocalExecutionSandboxFactory,
)


@dataclass(slots=True)
class AgentExecutionRequest:
    task_id: str
    run_id: str
    objective: str
    workspace_roots: list[str]
    identity_bundle_text: str
    sandbox: ExecutionSandbox
    allowed_capabilities: list[str]
    metadata: dict[str, Any]
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    checkpoint_controller: CheckpointController | None = None
    resume_from_checkpoint_id: str | None = None


@dataclass(slots=True)
class AgentExecutionResult:
    success: bool
    summary: str
    output_artifacts: list[str]
    error_message: str | None = None
    paused: bool = False
    pause_reason: str | None = None


class AgentHarness(Protocol):
    def execute(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> AgentExecutionResult: ...


class StubAgentHarness:
    def __init__(
        self,
        *,
        success: bool = True,
        summary: str | None = None,
        output_artifact_path: str | None = None,
        output_artifact_content: str = "# Runtime Artifact\n",
    ) -> None:
        self._success = success
        self._summary = summary
        self._output_artifact_path = output_artifact_path
        self._output_artifact_content = output_artifact_content

    def execute(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> AgentExecutionResult:
        if self._success:
            output_artifacts: list[str] = []
            if self._output_artifact_path is not None:
                request.sandbox.write_text(
                    self._output_artifact_path, self._output_artifact_content
                )
                output_artifacts.append(request.sandbox.normalize_path(self._output_artifact_path))
            summary = self._summary or "Stub harness completed without external execution."
            return AgentExecutionResult(
                success=True,
                summary=summary,
                output_artifacts=output_artifacts,
            )
        summary = self._summary or "Stub harness failed before external execution."
        return AgentExecutionResult(
            success=False,
            summary=summary,
            output_artifacts=[],
            error_message="stub harness failure",
        )


class TaskRunner:
    def __init__(
        self,
        run_state_store: RunStateStore,
        event_bus: EventBus,
        artifact_store: ArtifactStore,
        sandbox_factory: LocalExecutionSandboxFactory,
        agent_harness: AgentHarness,
        durable_services: DurableRuntimeServices | None = None,
    ) -> None:
        self._run_state_store = run_state_store
        self._event_bus = event_bus
        self._artifact_store = artifact_store
        self._sandbox_factory = sandbox_factory
        self._agent_harness = agent_harness
        self._durable_services = durable_services
        self._source = EventSource(kind=EventSourceKind.RUNTIME, component="task-runner")
        self._checkpoint_adapter = (
            LangGraphCheckpointAdapter(durable_services.checkpoint_store)
            if durable_services is not None
            else None
        )

    def start_run(
        self,
        correlation_id: str | None,
        objective: str,
        workspace_roots: list[str],
        identity_bundle_text: str,
        allowed_capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        constraints: list[str] | None = None,
        success_criteria: list[str] | None = None,
    ) -> tuple[str, str, str]:
        task_id = new_task_id()
        run_id = new_run_id()
        accepted_at = utc_now_timestamp()
        state = RunState(
            task_id=task_id,
            run_id=run_id,
            status=TaskStatus.ACCEPTED,
            objective=objective,
            created_at=accepted_at,
            updated_at=accepted_at,
            accepted_at=accepted_at,
            workspace_roots=list(workspace_roots),
            allowed_capabilities=list(allowed_capabilities or []),
            metadata=dict(metadata or {}),
            constraints=list(constraints or []),
            success_criteria=list(success_criteria or []),
            current_phase="accepted",
            latest_summary="Task accepted by runtime.",
            awaiting_approval=False,
            is_resumable=False,
            checkpoint_thread_id=self._new_checkpoint_thread(task_id, run_id),
            links={
                "artifacts": "task.artifacts.list",
                "resume": "task.resume",
                "events": "task.logs.stream",
            },
        )
        self._run_state_store.create(state)
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.TASK_CREATED.value,
            timestamp=accepted_at,
            source=self._source,
            payload={
                "status": TaskStatus.CREATED.value,
                "objective": objective,
                "workspace_roots": list(workspace_roots),
                "allowed_capabilities": list(allowed_capabilities or []),
                "metadata": dict(metadata or {}),
                "constraints": list(constraints or []),
                "success_criteria": list(success_criteria or []),
            },
        )
        self._execute_run(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            identity_bundle_text=identity_bundle_text,
            resume=False,
        )

        return task_id, run_id, accepted_at

    def resume_run(
        self,
        task_id: str,
        run_id: str | None = None,
        *,
        identity_bundle_text: str,
    ) -> TaskSnapshot:
        state = self._run_state_store.get(task_id, run_id)
        if state.status == TaskStatus.COMPLETED:
            raise ValueError("task.resume cannot resume a completed run")
        if state.status == TaskStatus.FAILED:
            raise ValueError("task.resume cannot resume a failed run")
        if not state.is_resumable:
            raise ValueError("task.resume requires a paused or resumable run")
        self._execute_run(
            task_id=state.task_id,
            run_id=state.run_id,
            correlation_id=None,
            identity_bundle_text=identity_bundle_text,
            resume=True,
        )
        return self.get_task_snapshot(state.task_id, state.run_id)

    def get_task_snapshot(self, task_id: str, run_id: str | None = None) -> TaskSnapshot:
        state = self._run_state_store.get(task_id, run_id)
        return TaskSnapshot(
            task_id=state.task_id,
            run_id=state.run_id,
            status=state.status,
            objective=state.objective,
            created_at=state.created_at,
            updated_at=state.updated_at,
            success_criteria=state.success_criteria or None,
            constraints=state.constraints or None,
            workspace_roots=state.workspace_roots or None,
            current_phase=state.current_phase,
            latest_summary=state.latest_summary,
            awaiting_approval=state.awaiting_approval,
            pending_approval_id=state.pending_approval_id,
            is_resumable=state.is_resumable,
            pause_reason=state.pause_reason,
            checkpoint_thread_id=state.checkpoint_thread_id,
            latest_checkpoint_id=state.latest_checkpoint_id,
            active_subagent=state.active_subagent,
            artifact_count=state.artifact_count,
            last_event_at=state.last_event_at,
            failure=state.failure,
            links=state.links or None,
        )

    def list_artifacts(
        self,
        task_id: str,
        run_id: str | None = None,
        persistence_class: str | None = None,
        content_type_prefix: str | None = None,
    ) -> list:
        return self._artifact_store.list_artifacts(
            task_id,
            run_id,
            persistence_class=persistence_class,
            content_type_prefix=content_type_prefix,
        )

    @property
    def checkpoint_adapter(self) -> LangGraphCheckpointAdapter | None:
        return self._checkpoint_adapter

    def _execute_run(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        identity_bundle_text: str,
        resume: bool,
    ) -> None:
        state = self._run_state_store.get(task_id, run_id)
        started_at = utc_now_timestamp()
        checkpoint_controller = self._checkpoint_controller_for_run(task_id, run_id, resume)
        self._run_state_store.update(
            task_id,
            run_id,
            status=TaskStatus.EXECUTING,
            updated_at=started_at,
            current_phase="executing",
            latest_summary="Agent harness execution started."
            if not resume
            else "Runtime resumed execution from the latest checkpoint metadata.",
            last_event_at=started_at,
            awaiting_approval=False,
            is_resumable=False,
            pause_reason=None,
            checkpoint_thread_id=(
                checkpoint_controller.thread_id
                if checkpoint_controller is not None
                else state.checkpoint_thread_id
            ),
            latest_checkpoint_id=(
                checkpoint_controller.latest_checkpoint_id
                if checkpoint_controller is not None
                else state.latest_checkpoint_id
            ),
        )
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.TASK_RESUMED.value if resume else EventType.TASK_STARTED.value,
            timestamp=started_at,
            source=self._source,
            payload={
                "status": TaskStatus.EXECUTING.value,
                "started_at": started_at,
                "thread_id": checkpoint_controller.thread_id
                if checkpoint_controller is not None
                else None,
                "latest_checkpoint_id": (
                    checkpoint_controller.latest_checkpoint_id
                    if checkpoint_controller is not None
                    else state.latest_checkpoint_id
                ),
                "summary": (
                    "Execution resumed from the latest checkpoint."
                    if resume
                    else "Agent harness execution started."
                ),
            },
        )
        if resume:
            self._increment_resume_metrics(task_id, run_id)

        sandbox = self._sandbox_factory.for_run(
            task_id=task_id,
            run_id=run_id,
            workspace_roots=state.workspace_roots,
        )
        try:
            result = self._agent_harness.execute(
                AgentExecutionRequest(
                    task_id=task_id,
                    run_id=run_id,
                    objective=state.objective,
                    workspace_roots=list(state.workspace_roots),
                    identity_bundle_text=identity_bundle_text,
                    sandbox=sandbox,
                    allowed_capabilities=list(state.allowed_capabilities),
                    metadata=dict(state.metadata),
                    constraints=list(state.constraints),
                    success_criteria=list(state.success_criteria),
                    checkpoint_controller=checkpoint_controller,
                    resume_from_checkpoint_id=(
                        checkpoint_controller.latest_checkpoint_id
                        if checkpoint_controller is not None
                        else None
                    ),
                ),
                on_event=lambda event_type, payload: self._handle_harness_event(
                    task_id=task_id,
                    run_id=run_id,
                    correlation_id=correlation_id,
                    event_type=event_type,
                    payload=payload,
                ),
            )
        except Exception as exc:
            self._append_diagnostic(
                task_id=task_id,
                run_id=run_id,
                kind="agent_harness_error",
                message=str(exc),
                details={"phase": "execute", "resume": resume},
            )
            result = AgentExecutionResult(
                success=False,
                summary="Agent harness raised an unexpected error.",
                output_artifacts=[],
                error_message=str(exc),
            )

        artifact_count = state.artifact_count
        for sandbox_path in result.output_artifacts:
            artifact = self._artifact_store.register_artifact(
                task_id=task_id,
                run_id=run_id,
                sandbox_path=sandbox_path,
            )
            artifact_count += 1
            registered_at = utc_now_timestamp()
            self._run_state_store.update(
                task_id,
                run_id,
                updated_at=registered_at,
                artifact_count=artifact_count,
                last_event_at=registered_at,
            )
            self._publish(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                event_type=EventType.ARTIFACT_CREATED.value,
                timestamp=registered_at,
                source=EventSource(kind=EventSourceKind.RUNTIME, component="artifact-store"),
                payload={"artifact": artifact.to_dict()},
            )

        if result.paused:
            paused_at = utc_now_timestamp()
            self._run_state_store.update(
                task_id,
                run_id,
                status=TaskStatus.PAUSED,
                updated_at=paused_at,
                current_phase="paused",
                latest_summary=result.summary,
                artifact_count=artifact_count,
                last_event_at=paused_at,
                is_resumable=True,
                pause_reason=result.pause_reason or "execution paused",
            )
            self._publish(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                event_type=EventType.TASK_PAUSED.value,
                timestamp=paused_at,
                source=self._source,
                payload={
                    "status": TaskStatus.PAUSED.value,
                    "reason": result.pause_reason or "execution paused",
                    "summary": result.summary,
                },
            )
            return

        if result.success:
            completed_at = utc_now_timestamp()
            self._run_state_store.update(
                task_id,
                run_id,
                status=TaskStatus.COMPLETED,
                updated_at=completed_at,
                current_phase="completed",
                latest_summary=result.summary,
                artifact_count=artifact_count,
                last_event_at=completed_at,
                is_resumable=False,
                pause_reason=None,
            )
            self._publish(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                event_type=EventType.TASK_COMPLETED.value,
                timestamp=completed_at,
                source=self._source,
                payload={
                    "status": TaskStatus.COMPLETED.value,
                    "completed_at": completed_at,
                    "summary": result.summary,
                    "outcome": "success",
                    "artifact_count": artifact_count,
                },
            )
            return

        failed_at = utc_now_timestamp()
        self._append_diagnostic(
            task_id=task_id,
            run_id=run_id,
            kind="task_failure",
            message=result.error_message or result.summary,
            details={"summary": result.summary, "resume": resume},
        )
        self._run_state_store.update(
            task_id,
            run_id,
            status=TaskStatus.FAILED,
            updated_at=failed_at,
            current_phase="failed",
            latest_summary=result.summary,
            artifact_count=artifact_count,
            last_event_at=failed_at,
            failure=FailureInfo(message=result.error_message or result.summary),
            is_resumable=False,
            pause_reason=None,
        )
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.TASK_FAILED.value,
            timestamp=failed_at,
            source=self._source,
            payload={
                "status": TaskStatus.FAILED.value,
                "failed_at": failed_at,
                "summary": result.summary,
                "error": result.error_message or result.summary,
            },
        )

    def _publish(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        event_type: str,
        timestamp: str,
        source: EventSource,
        payload: dict[str, Any],
    ) -> None:
        runtime_event = RuntimeEvent(
            event=EventEnvelope(
                event_id=new_event_id(),
                event_type=event_type,
                timestamp=timestamp,
                correlation_id=correlation_id,
                task_id=task_id,
                run_id=run_id,
                source=source,
                payload=payload,
            )
        )
        self._event_bus.publish(runtime_event)
        if self._durable_services is not None:
            self._durable_services.event_store.append_event(runtime_event.event)

    def _handle_harness_event(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        timestamp = utc_now_timestamp()
        updates: dict[str, Any] = {
            "updated_at": timestamp,
            "last_event_at": timestamp,
        }
        phase = payload.get("phase")
        if isinstance(phase, str) and phase.strip():
            updates["current_phase"] = phase.strip()
        elif event_type == EventType.PLAN_UPDATED.value:
            updates["current_phase"] = "planning"
        elif event_type == EventType.SUBAGENT_STARTED.value:
            updates["current_phase"] = "executing"
            role = payload.get("role")
            if isinstance(role, str) and role.strip():
                updates["active_subagent"] = role.strip()
        summary = payload.get("summary")
        if isinstance(summary, str) and summary.strip():
            updates["latest_summary"] = summary.strip()
        if event_type == EventType.CHECKPOINT_SAVED.value:
            checkpoint_id = payload.get("checkpoint_id")
            thread_id = payload.get("thread_id")
            if isinstance(checkpoint_id, str) and checkpoint_id.strip():
                updates["latest_checkpoint_id"] = checkpoint_id
                updates["is_resumable"] = True
            if isinstance(thread_id, str) and thread_id.strip():
                updates["checkpoint_thread_id"] = thread_id
            self._increment_checkpoint_metrics(task_id, run_id)
        self._run_state_store.update(task_id, run_id, **updates)
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=event_type,
            timestamp=timestamp,
            source=_source_for_harness_event(event_type, payload),
            payload=payload,
        )

    def _append_diagnostic(
        self,
        *,
        task_id: str,
        run_id: str,
        kind: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        if self._durable_services is None:
            return
        self._durable_services.diagnostic_store.append_diagnostic(
            task_id=task_id,
            run_id=run_id,
            kind=kind,
            message=message,
            details=details or {},
        )

    def _new_checkpoint_thread(self, task_id: str, run_id: str) -> str | None:
        if self._checkpoint_adapter is None:
            return None
        return self._checkpoint_adapter.begin_run(task_id, run_id).thread_id

    def _checkpoint_controller_for_run(
        self,
        task_id: str,
        run_id: str,
        resume: bool,
    ) -> CheckpointController | None:
        if self._checkpoint_adapter is None:
            return None
        if resume:
            return self._checkpoint_adapter.resume_run(task_id, run_id)
        state = self._run_state_store.get(task_id, run_id)
        if state.checkpoint_thread_id is not None:
            return self._checkpoint_adapter.attach_thread(
                task_id,
                run_id,
                state.checkpoint_thread_id,
            )
        return self._checkpoint_adapter.begin_run(task_id, run_id)

    def _increment_checkpoint_metrics(self, task_id: str, run_id: str) -> None:
        if self._durable_services is None:
            return
        metrics = self._durable_services.run_metrics_store.read_metrics(task_id, run_id)
        checkpoint_count = 1 if metrics is None else metrics.checkpoint_count + 1
        approval_count = 0 if metrics is None else metrics.approval_count
        resume_count = 0 if metrics is None else metrics.resume_count
        self._durable_services.run_metrics_store.write_metrics(
            record=type(metrics)(
                task_id=task_id,
                run_id=run_id,
                checkpoint_count=checkpoint_count,
                approval_count=approval_count,
                resume_count=resume_count,
                last_updated_at=utc_now_timestamp(),
            )
            if metrics is not None
            else _run_metrics_record(
                task_id, run_id, checkpoint_count, approval_count, resume_count
            )
        )

    def _increment_resume_metrics(self, task_id: str, run_id: str) -> None:
        if self._durable_services is None:
            return
        metrics = self._durable_services.run_metrics_store.read_metrics(task_id, run_id)
        checkpoint_count = 0 if metrics is None else metrics.checkpoint_count
        approval_count = 0 if metrics is None else metrics.approval_count
        resume_count = 1 if metrics is None else metrics.resume_count + 1
        self._durable_services.run_metrics_store.write_metrics(
            record=type(metrics)(
                task_id=task_id,
                run_id=run_id,
                checkpoint_count=checkpoint_count,
                approval_count=approval_count,
                resume_count=resume_count,
                last_updated_at=utc_now_timestamp(),
            )
            if metrics is not None
            else _run_metrics_record(
                task_id, run_id, checkpoint_count, approval_count, resume_count
            )
        )


def _source_for_harness_event(event_type: str, payload: dict[str, Any]) -> EventSource:
    if event_type == EventType.SUBAGENT_STARTED.value:
        return EventSource(
            kind=EventSourceKind.SUBAGENT,
            role=str(payload.get("role", "primary")),
            name=str(payload.get("name", "primary-agent")),
            component="langchain-deepagent-harness",
        )
    if event_type == EventType.TOOL_CALLED.value:
        return EventSource(
            kind=EventSourceKind.TOOL,
            name=str(payload.get("tool", "sandbox-tool")),
            component="sandbox-tool-bindings",
        )
    return EventSource(kind=EventSourceKind.RUNTIME, component="langchain-deepagent-harness")


def _run_metrics_record(
    task_id: str,
    run_id: str,
    checkpoint_count: int,
    approval_count: int,
    resume_count: int,
) -> RunMetricsRecord:
    return RunMetricsRecord(
        task_id=task_id,
        run_id=run_id,
        checkpoint_count=checkpoint_count,
        approval_count=approval_count,
        resume_count=resume_count,
        last_updated_at=utc_now_timestamp(),
    )
