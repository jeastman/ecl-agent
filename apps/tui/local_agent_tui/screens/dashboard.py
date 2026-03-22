from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..compat import ComposeResult, Container, Horizontal, ListView, Screen, Static, Vertical, VerticalScroll, _TEXTUAL_IMPORT_ERROR
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
from ..widgets.loading import loading_renderable
from ..widgets.approval_queue import ApprovalQueueWidget
from ..widgets.status_bar import StatusBar
from ..widgets.task_list import TaskListRow, TaskListWidget
from ..widgets.toast import ToastRack
from ..theme.colors import ACCENT, DANGER, TEXT_MUTED_DEEP, WARNING


class DashboardScreen(Screen):  # type: ignore[misc]
    PANE_ORDER = ["tasks", "summary", "approvals", "artifacts"]

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
            ToastRack(id="toast-rack"),
            id="dashboard-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        if state.runtime_snapshot_status == "loading" and not state.task_snapshots:
            tasks_focused = state.focused_pane == "tasks"
            approvals_focused = state.focused_pane == "approvals"
            artifacts_focused = state.focused_pane == "artifacts"
            summary_focused = state.focused_pane == "summary"
            self.query_one(TaskListWidget).show_loading("Loading tasks...", focused=tasks_focused)
            self.query_one(ApprovalQueueWidget).show_loading(
                "Loading approvals...",
                focused=approvals_focused,
                inbox_mode=False,
            )
            task_summary = self.query_one("#task-summary", VerticalScroll)
            task_summary.border_title = _pane_title(2, "Selected Task", focused=summary_focused)
            task_summary.border_subtitle = "Loading"
            task_summary.set_class(summary_focused, "-focused-pane")
            self.query_one("#task-summary-content", Static).update(
                loading_renderable("Loading dashboard summary...", skeleton_lines=5)
            )
            artifacts_pane = self.query_one("#recent-artifacts", Static)
            artifacts_pane.border_title = _pane_title(4, "Recent Artifacts", focused=artifacts_focused)
            artifacts_pane.border_subtitle = "Loading"
            artifacts_pane.set_class(artifacts_focused, "-focused-pane")
            artifacts_pane.update(loading_renderable("Loading artifacts...", skeleton_lines=4))
            self.query_one(TaskListWidget).border_title = _pane_title(1, "Tasks", focused=tasks_focused)
            self.query_one(ApprovalQueueWidget).border_title = _pane_title(3, "Approvals Pending", focused=approvals_focused)
            self.query_one("#dashboard-footer", Static).update(footer_hints(state, contextual=True))
            return
        tasks = recent_tasks(state)
        tasks_focused = state.focused_pane == "tasks"
        approvals_focused = state.focused_pane == "approvals"
        summary_focused = state.focused_pane == "summary"
        artifacts_focused = state.focused_pane == "artifacts"
        task_list = self.query_one(TaskListWidget)
        task_list.update_tasks(tasks, focused=tasks_focused)
        task_list.border_title = _pane_title(1, "Tasks", focused=tasks_focused)
        self.query_one(ApprovalQueueWidget).update_approvals(
            pending_approvals_for_selected_task(state, limit=5),
            focused=approvals_focused,
            inbox_mode=False,
        )
        self.query_one(ApprovalQueueWidget).border_title = _pane_title(3, "Approvals Pending", focused=approvals_focused)
        task_summary = self.query_one("#task-summary", VerticalScroll)
        task_summary.border_title = _pane_title(2, "Selected Task", focused=summary_focused)
        task_summary.border_subtitle = (
            "Focused" if summary_focused else "Active Task"
        )
        task_summary.set_class(summary_focused, "-focused-pane")
        self.query_one("#task-summary-content", Static).update(_task_summary_renderable(state))
        artifacts_pane = self.query_one("#recent-artifacts", Static)
        artifacts_pane.border_title = _pane_title(4, "Recent Artifacts", focused=artifacts_focused)
        artifacts_pane.border_subtitle = "Focused" if artifacts_focused else ""
        artifacts_pane.set_class(artifacts_focused, "-focused-pane")
        artifacts = recent_artifacts(state)
        artifacts_pane.update(_recent_artifacts_renderable(artifacts))
        self.query_one("#dashboard-footer", Static).update(footer_hints(state, contextual=True))

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


def _task_summary_renderable(state: AppState) -> Text | Group:
    empty_state = dashboard_empty_state(state)
    if empty_state is not None:
        if state.connection_status == "error":
            text = render_empty_state("tasks")
            text.append("\n")
            text.append(state.last_error or "Runtime connection failed.", style=DANGER)
            return text
        text = render_empty_state("tasks")
        text.append("\n\n")
        text.append("Welcome\n", style="bold")
        text.append("Press N to create a task, G to open the command palette, or ? for help.", style=TEXT_MUTED_DEEP)
        return text
    summary = selected_task_summary(state)
    if summary is None:
        text = render_empty_state("tasks")
        text.append("\n")
        text.append("Select a task to view its summary.", style=TEXT_MUTED_DEEP)
        return text
    return _task_summary_text(summary)


def _task_summary_text(summary: TaskSummaryViewModel) -> Group:
    metadata = Table.grid(padding=(0, 2))
    metadata.add_column(style=TEXT_MUTED_DEEP, width=10)
    metadata.add_column(style="default")
    metadata.add_row("Task", truncate_id(summary.task_id, width=24))
    metadata.add_row("Run", summary.run_id or "unknown")
    metadata.add_row("Created", compact_datetime(summary.created_at))
    metadata.add_row("Updated", compact_datetime(summary.updated_at))
    metadata.add_row("Artifacts", str(summary.artifact_count))

    status_line = Text()
    status_line.append_text(status_badge(summary.status))
    status_line.append("  ")
    status_line.append_text(label("Next: "))
    status_line.append_text(value(summary.actionable_label))
    status_panel = Panel(status_line, title="Status", border_style=ACCENT)

    objective = Text()
    objective.append_text(title("Objective"))
    objective.append("\n")
    objective.append(truncate(summary.objective or "No objective available.", 240))

    latest = Text()
    latest.append_text(title("Latest Summary"))
    latest.append("\n")
    latest.append(truncate(summary.latest_summary, 240))

    hint = Text()
    hint.append_text(muted(summary.actionable_hint))
    if summary.awaiting_approval:
        hint.append("\n")
        hint.append("Approval required before the task can continue.", style=WARNING)

    metadata_group = Group(title("Metadata"), metadata)
    return Group(status_panel, objective, latest, metadata_group, hint)


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


def _pane_title(number: int, title_text: str, *, focused: bool) -> str:
    glyph = {1: "①", 2: "②", 3: "③", 4: "④"}.get(number, str(number))
    return f"{glyph} {title_text}" if not focused else f"> {glyph} {title_text}"
