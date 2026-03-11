from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from apps.runtime.local_agent_runtime.artifact_store import ArtifactStore
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


@dataclass(slots=True)
class AgentExecutionResult:
    success: bool
    summary: str
    output_artifacts: list[str]
    error_message: str | None = None


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
    ) -> None:
        self._run_state_store = run_state_store
        self._event_bus = event_bus
        self._artifact_store = artifact_store
        self._sandbox_factory = sandbox_factory
        self._agent_harness = agent_harness
        self._source = EventSource(kind=EventSourceKind.RUNTIME, component="task-runner")

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
            constraints=list(constraints or []),
            success_criteria=list(success_criteria or []),
            current_phase="accepted",
            latest_summary="Task accepted by runtime.",
            links={
                "artifacts": "task.artifacts.list",
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
            payload={"status": TaskStatus.CREATED.value, "objective": objective},
        )

        started_at = utc_now_timestamp()
        self._run_state_store.update(
            task_id,
            run_id,
            status=TaskStatus.EXECUTING,
            updated_at=started_at,
            current_phase="executing",
            latest_summary="Stub harness execution started.",
            last_event_at=started_at,
        )
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.TASK_STARTED.value,
            timestamp=started_at,
            payload={"status": TaskStatus.EXECUTING.value, "started_at": started_at},
        )

        sandbox = self._sandbox_factory.for_run(
            task_id=task_id,
            run_id=run_id,
            workspace_roots=workspace_roots,
        )
        result = self._agent_harness.execute(
            AgentExecutionRequest(
                task_id=task_id,
                run_id=run_id,
                objective=objective,
                workspace_roots=list(workspace_roots),
                identity_bundle_text=identity_bundle_text,
                sandbox=sandbox,
                allowed_capabilities=list(allowed_capabilities or []),
                metadata=dict(metadata or {}),
                constraints=list(constraints or []),
                success_criteria=list(success_criteria or []),
            )
        )

        artifact_count = 0
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
                payload={"artifact": artifact.to_dict()},
            )

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
            )
            self._publish(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                event_type=EventType.TASK_COMPLETED.value,
                timestamp=completed_at,
                payload={
                    "status": TaskStatus.COMPLETED.value,
                    "completed_at": completed_at,
                    "summary": result.summary,
                    "outcome": "success",
                    "artifact_count": artifact_count,
                },
            )
        else:
            failed_at = utc_now_timestamp()
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
            )
            self._publish(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                event_type=EventType.TASK_FAILED.value,
                timestamp=failed_at,
                payload={
                    "status": TaskStatus.FAILED.value,
                    "failed_at": failed_at,
                    "summary": result.summary,
                    "error": result.error_message or result.summary,
                },
            )

        return task_id, run_id, accepted_at

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

    def _publish(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        event_type: str,
        timestamp: str,
        payload: dict[str, Any],
    ) -> None:
        self._event_bus.publish(
            RuntimeEvent(
                event=EventEnvelope(
                    event_id=new_event_id(),
                    event_type=event_type,
                    timestamp=timestamp,
                    correlation_id=correlation_id,
                    task_id=task_id,
                    run_id=run_id,
                    source=self._source,
                    payload=payload,
                )
            )
        )
