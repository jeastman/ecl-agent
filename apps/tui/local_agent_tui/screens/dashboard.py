from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.table import Table
from rich.text import Text

from ..renderables import badge, block, highlighted_row, join, metadata_line, muted, text
from ..store.app_state import AppState
from ..store.selectors import (
    ArtifactItemViewModel,
    TaskSummaryViewModel,
    dashboard_empty_state,
    footer_hints,
    pending_approvals_for_selected_task,
    recent_artifacts,
    recent_tasks,
    selected_task_summary,
)
from ..theme.empty_states import render_empty_state
from ..theme.typography import label, muted, status_badge, title, value
from ..utils.time_format import compact_datetime
from ..utils.text import truncate_id
from ..utils.text import truncate
from ..widgets.approval_queue import ApprovalQueueWidget
from ..widgets.status_bar import StatusBar
from ..widgets.task_list import TaskListRow, TaskListWidget
from ..theme.colors import ACCENT, DANGER, TEXT_MUTED_DEEP, WARNING

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
            Static(id="dashboard-footer", markup=False),
            id="dashboard-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        tasks = recent_tasks(state)
        self.query_one(TaskListWidget).update_tasks(tasks, focused=state.focused_pane == "tasks")
        self.query_one(ApprovalQueueWidget).update_approvals(
            pending_approvals_for_selected_task(state, limit=5),
            focused=state.focused_pane == "approvals",
            inbox_mode=False,
        )
        task_summary = self.query_one("#task-summary", VerticalScroll)
        task_summary.border_title = "Selected Task"
        task_summary.border_subtitle = (
            "Focused" if state.focused_pane == "summary" else "Active Task"
        )
        task_summary.set_class(state.focused_pane == "summary", "-focused-pane")
        self.query_one("#task-summary-content", Static).update(_task_summary_renderable(state))
        artifacts_pane = self.query_one("#recent-artifacts", Static)
        artifacts_pane.border_title = "Recent Artifacts"
        artifacts_pane.border_subtitle = "Focused" if state.focused_pane == "artifacts" else ""
        artifacts_pane.set_class(state.focused_pane == "artifacts", "-focused-pane")
        artifacts = recent_artifacts(state)
        artifacts_pane.update(_recent_artifacts_renderable(artifacts))
        self.query_one("#dashboard-footer", Static).update(footer_hints(state))

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


def _task_summary_renderable(state: AppState) -> Text:
    empty_state = dashboard_empty_state(state)
    if empty_state is not None:
        if state.connection_status == "error":
            text = render_empty_state("tasks")
            text.append("\n")
            text.append(state.last_error or "Runtime connection failed.", style=DANGER)
            return text
        return render_empty_state("tasks")
    summary = selected_task_summary(state)
    if summary is None:
        text = render_empty_state("tasks")
        text.append("\n")
        text.append("Select a task to view its summary.", style=TEXT_MUTED_DEEP)
        return text
    return _task_summary_text(summary)


def _task_summary_text(summary: TaskSummaryViewModel) -> Text:
    metadata = Table.grid(padding=(0, 2))
    metadata.add_column(style=TEXT_MUTED_DEEP, width=10)
    metadata.add_column(style="default")
    metadata.add_row("Task", truncate_id(summary.task_id, width=24))
    metadata.add_row("Run", summary.run_id or "unknown")
    metadata.add_row("Created", compact_datetime(summary.created_at))
    metadata.add_row("Updated", compact_datetime(summary.updated_at))
    metadata.add_row("Artifacts", str(summary.artifact_count))

    text = Text()
    text.append_text(status_badge(summary.status))
    text.append("  ")
    text.append_text(label("Next: "))
    text.append_text(value(summary.actionable_label))
    text.append("\n\n")
    text.append_text(title("Objective"))
    text.append("\n")
    text.append(truncate(summary.objective or "No objective available.", 240))
    text.append("\n\n")
    text.append_text(title("Latest Summary"))
    text.append("\n")
    text.append(truncate(summary.latest_summary, 240))
    text.append("\n\n")
    text.append_text(title("Metadata"))
    text.append("\n")
    text.append(str(metadata))
    text.append("\n\n")
    text.append_text(muted(summary.actionable_hint))
    if summary.awaiting_approval:
        text.append("\n\n")
        text.append("Approval required before the task can continue.", style=WARNING)
    return text


def _recent_artifacts_renderable(artifacts: list[ArtifactItemViewModel]) -> Text:
    if not artifacts:
        return render_empty_state("artifacts")
    text = Text()
    for index, artifact in enumerate(artifacts):
        if index:
            text.append("\n\n")
        text.append_text(_artifact_card(artifact))
    return text


def _artifact_card(artifact: ArtifactItemViewModel) -> Text:
    text = Text()
    text.append(f"{_artifact_icon(artifact)} ", style=ACCENT)
    text.append(truncate(artifact.display_name, 24), style="bold")
    text.append("  ")
    text.append(truncate(_artifact_type_label(artifact.content_type), 10), style=TEXT_MUTED_DEEP)
    text.append("  ")
    text.append(artifact.created_at_relative, style=TEXT_MUTED_DEEP)
    return text


def _artifact_icon(artifact: ArtifactItemViewModel) -> str:
    content_type = artifact.content_type.lower()
    name = artifact.display_name.lower()
    if "markdown" in content_type or name.endswith(".md"):
        return "📝"
    if "yaml" in content_type or name.endswith((".yaml", ".yml")):
        return "📄"
    if "json" in content_type or name.endswith(".json"):
        return "📋"
    if name.endswith(".py") or "python" in content_type:
        return "💻"
    if "image" in content_type:
        return "🖼"
    return "📎"


def _artifact_type_label(content_type: str) -> str:
    lowered = content_type.lower()
    if "markdown" in lowered:
        return "markdown"
    if "yaml" in lowered:
        return "yaml"
    if "json" in lowered:
        return "json"
    if "python" in lowered:
        return "python"
    return content_type
