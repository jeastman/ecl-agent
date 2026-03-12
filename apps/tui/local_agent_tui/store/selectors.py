from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from .app_state import AppState, TaskEventRecord


@dataclass(frozen=True, slots=True)
class TaskListItemViewModel:
    task_id: str
    run_id: str
    status: str
    objective: str
    updated_at: str
    awaiting_approval: bool
    artifact_count: int
    is_selected: bool


@dataclass(frozen=True, slots=True)
class TaskSummaryViewModel:
    task_id: str
    run_id: str
    status: str
    objective: str
    latest_summary: str
    created_at: str
    updated_at: str
    awaiting_approval: bool
    artifact_count: int


@dataclass(frozen=True, slots=True)
class ApprovalQueueItemViewModel:
    approval_id: str
    task_id: str
    run_id: str
    status: str
    request_type: str
    policy_context: str
    requested_action: str
    description: str
    scope_summary: str
    created_at: str
    is_selected: bool


@dataclass(frozen=True, slots=True)
class ApprovalDetailViewModel:
    approval_id: str
    task_id: str
    run_id: str
    request_type: str
    policy_context: str
    requested_action: str
    description: str
    scope_summary: str
    status: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ArtifactItemViewModel:
    artifact_id: str
    task_id: str
    run_id: str
    logical_path: str
    display_name: str
    content_type: str
    created_at: str


@dataclass(frozen=True, slots=True)
class TaskDetailHeaderViewModel:
    task_id: str
    run_id: str
    status: str
    created_at: str
    updated_at: str
    objective: str
    current_phase: str
    active_subagent: str | None


@dataclass(frozen=True, slots=True)
class TimelineEventViewModel:
    timestamp: str
    event_type: str
    summary: str
    severity: str
    repeat_count: int
    source_name: str | None


@dataclass(frozen=True, slots=True)
class TimelineGroupViewModel:
    events: list[TimelineEventViewModel]


@dataclass(frozen=True, slots=True)
class PlanHistoryItemViewModel:
    timestamp: str
    summary: str
    phase: str


@dataclass(frozen=True, slots=True)
class PlanViewModel:
    current_phase: str
    current_step: str
    recent_updates: list[PlanHistoryItemViewModel]


@dataclass(frozen=True, slots=True)
class SubagentActivityItemViewModel:
    subagent_id: str
    status: str
    started_at: str | None
    completed_at: str | None
    latest_summary: str


@dataclass(frozen=True, slots=True)
class ArtifactPanelItemViewModel:
    artifact_id: str
    display_name: str
    logical_path: str
    content_type: str
    created_at: str
    is_selected: bool


@dataclass(frozen=True, slots=True)
class TaskActionBarViewModel:
    resume_enabled: bool
    approvals_enabled: bool
    artifact_open_enabled: bool
    back_enabled: bool
    command_text: str


@dataclass(frozen=True, slots=True)
class NotificationStripItemViewModel:
    timestamp: str
    summary: str
    severity: str


@dataclass(frozen=True, slots=True)
class NotificationStripViewModel:
    items: list[NotificationStripItemViewModel]


def connection_label(state: AppState) -> str:
    if state.last_error:
        return f"{state.connection_status} ({state.last_error})"
    return state.connection_status


def runtime_health_label(state: AppState) -> str:
    if not state.runtime_health:
        return "unknown"
    return str(state.runtime_health.get("status", "unknown"))


def task_count(state: AppState) -> int:
    return len(_sorted_task_snapshots(state))


def approval_count(state: AppState) -> int:
    return len(pending_approvals(state))


def artifact_count(state: AppState) -> int:
    return sum(len(artifacts) for artifacts in state.artifacts_by_task.values())


def recent_task_ids(state: AppState) -> list[str]:
    return [str(task["task_id"]) for task in _sorted_task_snapshots(state)]


def recent_tasks(state: AppState, *, limit: int = 10) -> list[TaskListItemViewModel]:
    items: list[TaskListItemViewModel] = []
    for task in _sorted_task_snapshots(state)[:limit]:
        items.append(
            TaskListItemViewModel(
                task_id=str(task["task_id"]),
                run_id=str(task.get("run_id", "")),
                status=str(task.get("status", "unknown")),
                objective=str(task.get("objective", "")),
                updated_at=str(task.get("last_event_at") or task.get("updated_at") or ""),
                awaiting_approval=bool(task.get("awaiting_approval", False)),
                artifact_count=_int_value(task.get("artifact_count", 0)),
                is_selected=state.selected_task_id == task["task_id"],
            )
        )
    return items


def running_tasks(state: AppState) -> list[TaskListItemViewModel]:
    return [item for item in recent_tasks(state) if item.status in {"executing", "planning"}]


def selected_task_summary(state: AppState) -> TaskSummaryViewModel | None:
    if state.selected_task_id is None:
        return None
    task = state.task_snapshots.get(state.selected_task_id)
    if task is None:
        return None
    return TaskSummaryViewModel(
        task_id=str(task["task_id"]),
        run_id=str(task.get("run_id", "")),
        status=str(task.get("status", "unknown")),
        objective=str(task.get("objective", "")),
        latest_summary=str(task.get("latest_summary") or "Waiting for runtime updates."),
        created_at=str(task.get("created_at", "")),
        updated_at=str(task.get("last_event_at") or task.get("updated_at") or ""),
        awaiting_approval=bool(task.get("awaiting_approval", False)),
        artifact_count=_int_value(task.get("artifact_count", 0)),
    )


def selected_task_header(state: AppState) -> TaskDetailHeaderViewModel | None:
    task = _selected_task(state)
    if task is None:
        return None
    return TaskDetailHeaderViewModel(
        task_id=str(task["task_id"]),
        run_id=str(task.get("run_id", "")),
        status=str(task.get("status", "unknown")),
        created_at=str(task.get("created_at", "")),
        updated_at=str(task.get("last_event_at") or task.get("updated_at") or ""),
        objective=str(task.get("objective", "")),
        current_phase=str(task.get("current_phase") or "unknown"),
        active_subagent=_str_or_none(task.get("active_subagent")),
    )


def pending_approvals(
    state: AppState,
    *,
    limit: int | None = None,
) -> list[ApprovalQueueItemViewModel]:
    approvals: list[ApprovalQueueItemViewModel] = []
    for entries in state.approvals_by_task.values():
        for approval in entries:
            status = str(approval.get("status", "pending"))
            if status not in {"pending", "waiting"}:
                continue
            approval_id = str(approval.get("approval_id", ""))
            approvals.append(
                ApprovalQueueItemViewModel(
                    approval_id=approval_id,
                    task_id=str(approval.get("task_id", "")),
                    run_id=str(approval.get("run_id", "")),
                    status=status,
                    request_type=_approval_request_type(approval),
                    policy_context=_approval_policy_context(approval),
                    requested_action=_approval_requested_action(approval),
                    description=str(
                        approval.get("description") or approval.get("type") or "Approval"
                    ),
                    scope_summary=str(approval.get("scope_summary") or "Pending review"),
                    created_at=str(approval.get("created_at", "")),
                    is_selected=state.selected_approval_id == approval_id,
                )
            )
    approvals.sort(key=lambda item: item.created_at, reverse=True)
    if limit is not None:
        approvals = approvals[:limit]
    return approvals


def selected_approval_detail(state: AppState) -> ApprovalDetailViewModel | None:
    approval = _selected_approval(state)
    if approval is None:
        return None
    return ApprovalDetailViewModel(
        approval_id=str(approval.get("approval_id", "")),
        task_id=str(approval.get("task_id", "")),
        run_id=str(approval.get("run_id", "")),
        request_type=_approval_request_type(approval),
        policy_context=_approval_policy_context(approval),
        requested_action=_approval_requested_action(approval),
        description=str(approval.get("description") or approval.get("type") or "Approval"),
        scope_summary=str(approval.get("scope_summary") or "Pending review"),
        status=str(approval.get("status", "pending")),
        created_at=str(approval.get("created_at", "")),
    )


def recent_artifacts(state: AppState, *, limit: int = 5) -> list[ArtifactItemViewModel]:
    artifacts: list[ArtifactItemViewModel] = []
    for entries in state.artifacts_by_task.values():
        for artifact in entries:
            artifacts.append(_artifact_item_view_model(artifact))
    artifacts.sort(key=lambda item: item.created_at, reverse=True)
    return artifacts[:limit]


def task_timeline(state: AppState) -> TimelineGroupViewModel:
    events = _selected_task_events(state)
    collapsed: list[TimelineEventViewModel] = []
    for event in events:
        current = _timeline_event(event)
        previous = collapsed[-1] if collapsed else None
        if (
            previous is not None
            and previous.event_type == current.event_type
            and previous.summary == current.summary
        ):
            collapsed[-1] = TimelineEventViewModel(
                timestamp=previous.timestamp,
                event_type=previous.event_type,
                summary=previous.summary,
                severity=previous.severity,
                repeat_count=previous.repeat_count + 1,
                source_name=previous.source_name,
            )
            continue
        collapsed.append(current)
    return TimelineGroupViewModel(events=collapsed)


def task_plan_view(state: AppState) -> PlanViewModel:
    task = _selected_task(state)
    if task is None:
        return PlanViewModel(
            current_phase="unknown",
            current_step="No task selected.",
            recent_updates=[],
        )
    plan_events = [
        event for event in _selected_task_events(state) if event.event_type == "plan.updated"
    ]
    recent_updates = [
        PlanHistoryItemViewModel(
            timestamp=event.timestamp,
            summary=event.summary,
            phase=str(event.payload.get("phase") or task.get("current_phase") or "unknown"),
        )
        for event in plan_events[-5:]
    ]
    current_step = (
        recent_updates[-1].summary
        if recent_updates
        else str(task.get("latest_summary") or "Waiting for plan updates.")
    )
    return PlanViewModel(
        current_phase=str(task.get("current_phase") or "unknown"),
        current_step=current_step,
        recent_updates=recent_updates,
    )


def task_subagent_activity(state: AppState) -> list[SubagentActivityItemViewModel]:
    items: dict[str, SubagentActivityItemViewModel] = {}
    for event in _selected_task_events(state):
        subagent_id = _subagent_id(event)
        if subagent_id is None:
            continue
        current = items.get(
            subagent_id,
            SubagentActivityItemViewModel(
                subagent_id=subagent_id,
                status="UNKNOWN",
                started_at=None,
                completed_at=None,
                latest_summary="",
            ),
        )
        if event.event_type == "subagent.started":
            items[subagent_id] = SubagentActivityItemViewModel(
                subagent_id=subagent_id,
                status="RUNNING",
                started_at=event.timestamp,
                completed_at=current.completed_at,
                latest_summary=str(event.payload.get("taskDescription") or event.summary),
            )
        elif event.event_type == "subagent.completed":
            items[subagent_id] = SubagentActivityItemViewModel(
                subagent_id=subagent_id,
                status=str(event.payload.get("status", "completed")).upper(),
                started_at=current.started_at,
                completed_at=event.timestamp,
                latest_summary=str(event.payload.get("summary") or event.summary),
            )
    return list(items.values())


def task_artifact_panel(state: AppState) -> list[ArtifactPanelItemViewModel]:
    task_key = _selected_task_key(state)
    if task_key is None:
        return []
    selected_artifact_id = state.selected_artifact_id_by_task.get(task_key)
    artifacts = list(state.artifacts_by_task.get(task_key, []))
    artifacts.sort(key=lambda artifact: str(artifact.get("created_at", "")), reverse=True)
    return [
        ArtifactPanelItemViewModel(
            artifact_id=str(artifact.get("artifact_id", "")),
            display_name=str(
                artifact.get("display_name")
                or artifact.get("logical_path")
                or artifact.get("artifact_id")
                or "artifact"
            ),
            logical_path=str(artifact.get("logical_path", "")),
            content_type=str(artifact.get("content_type", "unknown")),
            created_at=str(artifact.get("created_at", "")),
            is_selected=str(artifact.get("artifact_id", "")) == selected_artifact_id,
        )
        for artifact in artifacts
    ]


def task_notifications(state: AppState) -> NotificationStripViewModel:
    priority_events = [
        event
        for event in _selected_task_events(state)
        if event.event_type
        in {
            "approval.requested",
            "task.failed",
            "artifact.created",
            "task.completed",
            "task.resumed",
        }
    ]
    priority_events = priority_events[-3:]
    return NotificationStripViewModel(
        items=[
            NotificationStripItemViewModel(
                timestamp=event.timestamp,
                summary=event.summary,
                severity=event.severity,
            )
            for event in priority_events
        ]
    )


def task_action_bar(state: AppState) -> TaskActionBarViewModel:
    task = _selected_task(state)
    artifacts = task_artifact_panel(state)
    approvals_enabled = bool(selected_task_pending_approvals(state))
    resume_enabled = False
    command_text = ">"
    if task is not None:
        links = task.get("links", {})
        resume_enabled = bool(task.get("is_resumable")) or (
            isinstance(links, dict) and links.get("resume") == "task.resume"
        )
        command_text = "> resume" if resume_enabled else "> inspect"
    return TaskActionBarViewModel(
        resume_enabled=resume_enabled,
        approvals_enabled=approvals_enabled,
        artifact_open_enabled=bool(artifacts),
        back_enabled=True,
        command_text=command_text,
    )


def selected_task_pending_approvals(state: AppState) -> list[ApprovalQueueItemViewModel]:
    if state.selected_task_id is None:
        return []
    return [
        approval
        for approval in pending_approvals(state)
        if approval.task_id == state.selected_task_id
    ]


def footer_hints(state: AppState) -> list[str]:
    if state.active_screen == "approvals":
        return [
            "[A] Approve",
            "[R] Reject",
            "[Enter] Open Task",
            "[Esc] Dashboard",
            "[Q] Quit",
        ]
    if state.active_screen == "task_detail":
        action_bar = task_action_bar(state)
        hints = ["[Esc] Dashboard", "[A] Approvals", "[O] Artifact", "[Q] Quit"]
        if action_bar.resume_enabled:
            hints.insert(0, "[R] Resume")
        return hints
    if state.focused_pane == "approvals":
        return [
            "[Up/Down] Move Approval",
            "[Tab] Focus",
            "[Enter] Open Approvals",
            "[A] Approvals",
            "[Q] Quit",
        ]
    return [
        "[Up/Down] Move",
        "[Tab] Focus",
        "[Enter] Open Task",
        "[A] Approvals",
        "[Q] Quit",
    ]


def dashboard_empty_state(state: AppState) -> str | None:
    if state.connection_status == "error":
        return state.last_error or "Runtime connection failed."
    if not state.task_snapshots:
        return "No tasks available yet. Create or attach to a task to populate the dashboard."
    return None


def _selected_task(state: AppState) -> dict[str, Any] | None:
    if state.selected_task_id is None:
        return None
    return state.task_snapshots.get(state.selected_task_id)


def _selected_approval(state: AppState) -> dict[str, Any] | None:
    approval_id = state.selected_approval_id
    if approval_id is None:
        return None
    for entries in state.approvals_by_task.values():
        for approval in entries:
            if str(approval.get("approval_id", "")) == approval_id:
                return approval
    return None


def _selected_task_key(state: AppState) -> tuple[str, str] | None:
    task = _selected_task(state)
    if task is None or state.selected_task_id is None:
        return None
    run_id = task.get("run_id")
    if not isinstance(run_id, str):
        return None
    return (state.selected_task_id, run_id)


def _selected_task_events(state: AppState) -> list[TaskEventRecord]:
    task_key = _selected_task_key(state)
    if task_key is None:
        return []
    return list(state.run_event_buffers.get(task_key, []))


def _timeline_event(event: TaskEventRecord) -> TimelineEventViewModel:
    return TimelineEventViewModel(
        timestamp=event.timestamp,
        event_type=event.event_type,
        summary=event.summary,
        severity=event.severity,
        repeat_count=1,
        source_name=event.source_name,
    )


def _subagent_id(event: TaskEventRecord) -> str | None:
    value = event.payload.get("subagentId")
    if isinstance(value, str) and value.strip():
        return value
    return None


def _artifact_item_view_model(artifact: dict[str, Any]) -> ArtifactItemViewModel:
    return ArtifactItemViewModel(
        artifact_id=str(artifact.get("artifact_id", "")),
        task_id=str(artifact.get("task_id", "")),
        run_id=str(artifact.get("run_id", "")),
        logical_path=str(artifact.get("logical_path", "")),
        display_name=str(
            artifact.get("display_name")
            or artifact.get("logical_path")
            or artifact.get("artifact_id")
            or "artifact"
        ),
        content_type=str(artifact.get("content_type", "unknown")),
        created_at=str(artifact.get("created_at", "")),
    )


def _approval_request_type(approval: dict[str, Any]) -> str:
    value = approval.get("type")
    if isinstance(value, str) and value.strip():
        return value
    return "approval"


def _approval_policy_context(approval: dict[str, Any]) -> str:
    scope = approval.get("scope")
    if not isinstance(scope, dict) or not scope:
        return "unspecified"
    boundary_key = scope.get("boundary_key")
    if isinstance(boundary_key, str) and boundary_key.strip():
        return boundary_key
    kind = scope.get("kind")
    if isinstance(kind, str) and kind.strip():
        return kind
    first_key = next(iter(sorted(scope)))
    return str(first_key)


def _approval_requested_action(approval: dict[str, Any]) -> str:
    scope = approval.get("scope")
    if isinstance(scope, dict):
        for key in ("path_scope", "target_scope", "source_path", "memory_scope"):
            value = scope.get(key)
            if isinstance(value, str) and value.strip():
                return value
    scope_summary = approval.get("scope_summary")
    if isinstance(scope_summary, str) and scope_summary.strip():
        return scope_summary
    return _approval_request_type(approval)


def _sorted_task_snapshots(state: AppState) -> list[dict[str, Any]]:
    tasks = cast(list[dict[str, Any]], list(state.task_snapshots.values()))
    tasks.sort(
        key=lambda task: (
            str(task.get("last_event_at") or task.get("updated_at") or ""),
            str(task.get("updated_at") or ""),
            str(task.get("created_at") or ""),
        ),
        reverse=True,
    )
    return tasks


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    return 0


def _str_or_none(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
