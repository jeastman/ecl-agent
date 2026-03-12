from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import (
    dashboard_empty_state,
    footer_hints,
    pending_approvals,
    recent_artifacts,
    recent_tasks,
    selected_task_summary,
)
from ..widgets.approval_queue import ApprovalQueueWidget
from ..widgets.status_bar import StatusBar
from ..widgets.task_list import TaskListRow, TaskListWidget
from ..theme.colors import ACCENT, DANGER, SUCCESS, WARNING

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container, Horizontal, Vertical, VerticalScroll
    from textual.screen import Screen
    from textual.widgets import ListView, Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container, Horizontal, Vertical, VerticalScroll
        from textual.screen import Screen
        from textual.widgets import ListView, Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        Horizontal = cast(Any, object)
        Vertical = cast(Any, object)
        VerticalScroll = cast(Any, object)
        Screen = cast(Any, object)
        ListView = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class DashboardScreen(Screen):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            StatusBar(id="status-bar"),
            Horizontal(
                TaskListWidget(id="dashboard-task-list"),
                VerticalScroll(
                    Static(id="task-summary-content"),
                    id="task-summary",
                ),
                Vertical(
                    ApprovalQueueWidget(id="approval-queue"),
                    Static(id="recent-artifacts"),
                    id="dashboard-side-column",
                ),
                id="dashboard-main",
            ),
            Static(id="dashboard-footer"),
            id="dashboard-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        tasks = recent_tasks(state)
        self.query_one(TaskListWidget).update_tasks(tasks, focused=state.focused_pane == "tasks")
        self.query_one(ApprovalQueueWidget).update_approvals(
            pending_approvals(state, limit=5),
            focused=state.focused_pane == "approvals",
            inbox_mode=False,
        )
        task_summary = self.query_one("#task-summary", VerticalScroll)
        task_summary.border_title = "Selected Task"
        task_summary.border_subtitle = (
            "Focused" if state.focused_pane == "summary" else "Active Task"
        )
        task_summary.set_class(state.focused_pane == "summary", "-focused-pane")
        self.query_one("#task-summary-content", Static).update(_task_summary_text(state))
        artifacts_pane = self.query_one("#recent-artifacts", Static)
        artifacts_pane.border_title = "Recent Artifacts"
        artifacts_pane.border_subtitle = "Focused" if state.focused_pane == "artifacts" else ""
        artifacts_pane.set_class(state.focused_pane == "artifacts", "-focused-pane")
        artifacts = recent_artifacts(state)
        artifacts_pane.update(
            "\n".join(
                f"{artifact.task_id}  {artifact.display_name}\n{artifact.content_type}"
                for artifact in artifacts
            )
            or "No recent artifacts."
        )
        self.query_one("#dashboard-footer", Static).update("   ".join(footer_hints(state)))

    def on_list_view_highlighted(self, message: ListView.Highlighted) -> None:
        if message.list_view.id != "dashboard-task-list":
            return
        item = message.item
        if isinstance(item, TaskListRow):
            self.app.handle_dashboard_task_selected(item.task_id)  # type: ignore[attr-defined]

    def on_list_view_selected(self, message: ListView.Selected) -> None:
        if message.list_view.id != "dashboard-task-list":
            return
        self.app.action_open_task()  # type: ignore[attr-defined]


def _task_summary_text(state: AppState) -> str:
    empty_state = dashboard_empty_state(state)
    if empty_state is not None:
        return empty_state
    summary = selected_task_summary(state)
    if summary is None:
        return "Select a task to view its summary."
    lines = [
        f"Task: {summary.task_id}",
        f"Status: {_status_markup(summary.status)}",
        f"Next Action: {summary.actionable_label}",
        f"Run: {summary.run_id}",
        f"Created: {summary.created_at}",
        f"Updated: {summary.updated_at}",
        f"Artifacts: {summary.artifact_count}",
        "",
        "Objective",
        summary.objective or "No objective available.",
        "",
        "Latest Summary",
        summary.latest_summary,
        "",
        summary.actionable_hint,
    ]
    if summary.awaiting_approval:
        lines.extend(["", "Approval required before the task can continue."])
    return "\n".join(lines)


def _status_markup(status: str) -> str:
    color = {
        "executing": ACCENT,
        "planning": ACCENT,
        "running": ACCENT,
        "completed": SUCCESS,
        "failed": DANGER,
        "paused": WARNING,
        "awaiting_approval": WARNING,
    }.get(status.lower(), ACCENT)
    return f"[{color}]{status.upper()}[/]"
