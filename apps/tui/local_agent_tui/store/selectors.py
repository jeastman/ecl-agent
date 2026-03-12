from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from .app_state import AppState


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
    description: str
    scope_summary: str
    created_at: str
    is_selected: bool


@dataclass(frozen=True, slots=True)
class ArtifactItemViewModel:
    artifact_id: str
    task_id: str
    run_id: str
    logical_path: str
    display_name: str
    content_type: str
    created_at: str


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


def recent_artifacts(state: AppState, *, limit: int = 5) -> list[ArtifactItemViewModel]:
    artifacts: list[ArtifactItemViewModel] = []
    for entries in state.artifacts_by_task.values():
        for artifact in entries:
            artifacts.append(
                ArtifactItemViewModel(
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
            )
    artifacts.sort(key=lambda item: item.created_at, reverse=True)
    return artifacts[:limit]


def footer_hints(state: AppState) -> list[str]:
    if state.active_screen == "approvals":
        return ["[Esc] Dashboard", "[Enter] Open Task", "[Q] Quit"]
    if state.active_screen == "task_detail":
        return ["[Esc] Dashboard", "[A] Approvals", "[Q] Quit"]
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
