from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.runtime.local_agent_runtime.run_state_store import RunStateStore
from packages.protocol.local_agent_protocol.models import (
    EventEnvelope,
    EventSource,
    EventSourceKind,
    RuntimeEvent,
)
from packages.task_model.local_agent_task_model.ids import new_event_id
from packages.task_model.local_agent_task_model.models import (
    FailureInfo,
    RunState,
    TaskStatus,
    TodoItem,
    normalize_todos,
)
from services.checkpoint_service.local_agent_checkpoint_service.checkpoint_models import (
    ResumeHandle,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.checkpoint_adapter import (
    LangGraphCheckpointAdapter,
)
from services.observability_service.local_agent_observability_service.event_store import EventStore
from services.observability_service.local_agent_observability_service.observability_models import (
    PersistedEvent,
)


@dataclass(slots=True)
class RecoveryService:
    run_state_store: RunStateStore
    event_store: EventStore
    checkpoint_adapter: LangGraphCheckpointAdapter

    def recover(self) -> None:
        for task_id, run_id in self.event_store.list_run_keys():
            events = self.event_store.get_events(task_id, run_id)
            if not events:
                continue
            state = _rebuild_run_state(
                events,
                self.checkpoint_adapter,
            )
            self.run_state_store.create(state)
            if state.is_resumable:
                self.event_store.append_event(
                    PersistedEvent(
                        event_id=new_event_id(),
                        event_type="recovery.discovered",
                        timestamp=state.updated_at,
                        task_id=task_id,
                        run_id=run_id,
                        correlation_id=None,
                        source={"kind": "runtime", "component": "recovery-service"},
                        payload={
                            "status": state.status.value,
                            "latest_checkpoint_id": state.latest_checkpoint_id,
                            "thread_id": state.checkpoint_thread_id,
                            "summary": "Recovered resumable run metadata at runtime startup.",
                        },
                    )
                )


def _rebuild_run_state(
    events: list[PersistedEvent],
    checkpoint_adapter: LangGraphCheckpointAdapter,
) -> RunState:
    first_event = events[0]
    task_created = next(
        (event for event in events if event.event_type == "task.created"),
        first_event,
    )
    payload = task_created.payload
    task_id = first_event.task_id
    run_id = first_event.run_id
    resume_handle = _load_resume_handle(checkpoint_adapter, task_id, run_id)
    status = _status_from_events(events, resume_handle)
    latest_summary = _latest_summary(events)
    active_subagent = _latest_active_subagent(events)
    todos = _latest_todos(events)
    latest_checkpoint_id = resume_handle.latest_checkpoint_id if resume_handle is not None else None
    checkpoint_thread_id = resume_handle.thread_id if resume_handle is not None else None
    pause_reason = _pause_reason(events, status)
    pending_approval_id = (
        _pending_approval_id(events) if status == TaskStatus.AWAITING_APPROVAL else None
    )
    return RunState(
        task_id=task_id,
        run_id=run_id,
        status=status,
        objective=str(payload.get("objective", "")),
        created_at=task_created.timestamp,
        updated_at=events[-1].timestamp,
        accepted_at=task_created.timestamp,
        workspace_roots=_as_str_list(payload.get("workspace_roots")),
        allowed_capabilities=_as_str_list(payload.get("allowed_capabilities")),
        metadata=_as_dict(payload.get("metadata")),
        constraints=_as_str_list(payload.get("constraints")),
        success_criteria=_as_str_list(payload.get("success_criteria")),
        current_phase=_phase_from_events(events, status),
        latest_summary=latest_summary,
        active_subagent=active_subagent,
        todos=todos,
        artifact_count=sum(1 for event in events if event.event_type == "artifact.created"),
        last_event_at=events[-1].timestamp,
        failure=_failure_from_events(events),
        awaiting_approval=status == TaskStatus.AWAITING_APPROVAL,
        pending_approval_id=pending_approval_id,
        is_resumable=status in {TaskStatus.PAUSED, TaskStatus.AWAITING_APPROVAL}
        and latest_checkpoint_id is not None,
        pause_reason=pause_reason,
        checkpoint_thread_id=checkpoint_thread_id,
        latest_checkpoint_id=latest_checkpoint_id,
        links={
            "artifacts": "task.artifacts.list",
            "approve": "task.approve",
            "resume": "task.resume",
            "events": "task.logs.stream",
        },
    )


def persisted_event_to_runtime_event(record: PersistedEvent) -> RuntimeEvent:
    return RuntimeEvent(
        event=EventEnvelope(
            event_id=record.event_id,
            event_type=record.event_type,
            timestamp=record.timestamp,
            correlation_id=record.correlation_id,
            task_id=record.task_id,
            run_id=record.run_id,
            source=EventSource(
                kind=EventSourceKind(record.source.get("kind", "runtime")),
                name=_optional_str(record.source.get("name")),
                role=_optional_str(record.source.get("role")),
                component=_optional_str(record.source.get("component")),
            ),
            payload=record.payload,
        )
    )


def _load_resume_handle(
    checkpoint_adapter: LangGraphCheckpointAdapter,
    task_id: str,
    run_id: str,
) -> ResumeHandle | None:
    try:
        controller = checkpoint_adapter.resume_run(task_id, run_id)
    except ValueError:
        return None
    return ResumeHandle(
        task_id=task_id,
        run_id=run_id,
        thread_id=controller.thread_id,
        latest_checkpoint_id=controller.latest_checkpoint_id,
    )


def _status_from_events(
    events: list[PersistedEvent],
    resume_handle: ResumeHandle | None,
) -> TaskStatus:
    latest_type = events[-1].event_type
    if latest_type == "task.completed":
        return TaskStatus.COMPLETED
    if latest_type == "task.failed":
        return TaskStatus.FAILED
    if latest_type == "approval.requested" or _has_unresolved_approval(events):
        return TaskStatus.AWAITING_APPROVAL
    if latest_type == "task.paused":
        return TaskStatus.PAUSED
    if latest_type == "task.resumed":
        return TaskStatus.EXECUTING
    if resume_handle is not None and resume_handle.latest_checkpoint_id is not None:
        return TaskStatus.PAUSED
    return TaskStatus.EXECUTING


def _phase_from_events(events: list[PersistedEvent], status: TaskStatus) -> str:
    for event in reversed(events):
        phase = event.payload.get("phase")
        if isinstance(phase, str) and phase.strip():
            return phase.strip()
    if status == TaskStatus.AWAITING_APPROVAL:
        return "awaiting_approval"
    if status == TaskStatus.PAUSED:
        return "paused"
    if status == TaskStatus.COMPLETED:
        return "completed"
    if status == TaskStatus.FAILED:
        return "failed"
    return "executing"


def _latest_summary(events: list[PersistedEvent]) -> str | None:
    for event in reversed(events):
        if event.event_type == "recovery.discovered":
            continue
        for key in ("summary", "error"):
            value = event.payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _pause_reason(events: list[PersistedEvent], status: TaskStatus) -> str | None:
    if status == TaskStatus.AWAITING_APPROVAL:
        return "awaiting approval"
    for event in reversed(events):
        if event.event_type == "task.paused":
            reason = event.payload.get("reason")
            if isinstance(reason, str) and reason.strip():
                return reason.strip()
    return None


def _pending_approval_id(events: list[PersistedEvent]) -> str | None:
    for event in reversed(events):
        if event.event_type == "approval.requested":
            approval = event.payload.get("approval")
            if isinstance(approval, dict):
                approval_id = approval.get("approval_id")
                if isinstance(approval_id, str) and approval_id.strip():
                    return approval_id.strip()
    return None


def _has_unresolved_approval(events: list[PersistedEvent]) -> bool:
    latest_approval_index = -1
    latest_terminal_index = -1
    for index, event in enumerate(events):
        if event.event_type == "approval.requested":
            latest_approval_index = index
        if event.event_type in {"task.resumed", "task.failed", "task.completed"}:
            latest_terminal_index = index
    return latest_approval_index > latest_terminal_index


def _latest_active_subagent(events: list[PersistedEvent]) -> str | None:
    for event in reversed(events):
        if event.event_type == "subagent.completed":
            return None
        if event.event_type == "subagent.started":
            role = event.payload.get("role")
            if isinstance(role, str) and role.strip():
                return role.strip()
    return None


def _latest_todos(events: list[PersistedEvent]) -> list[TodoItem]:
    for event in reversed(events):
        if event.event_type != "tool.called":
            continue
        if str(event.payload.get("tool", "")).strip() != "write_todos":
            continue
        arguments = event.payload.get("arguments")
        if not isinstance(arguments, dict):
            return []
        return normalize_todos(arguments.get("todos"))
    return []


def _failure_from_events(events: list[PersistedEvent]) -> FailureInfo | None:
    for event in reversed(events):
        if event.event_type == "task.failed":
            message = event.payload.get("error") or event.payload.get("summary")
            if isinstance(message, str) and message.strip():
                return FailureInfo(message=message.strip())
    return None


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _as_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None
