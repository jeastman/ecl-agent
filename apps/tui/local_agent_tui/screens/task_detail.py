from __future__ import annotations

from rich.markup import escape

from ..compat import ComposeResult, Container, Horizontal, Key, Screen, Static, Vertical, _TEXTUAL_IMPORT_ERROR
from ..store.app_state import AppState
from ..store.selectors import (
    footer_hints,
    selected_remote_mcp_authorizations,
    selected_task_header,
    task_logs,
    task_action_bar,
    task_artifact_panel,
    task_notifications,
    task_plan_view,
    task_subagent_activity,
    task_todo_view,
    task_timeline,
    timeline_state_summary,
)
from ..widgets.artifact_panel import ArtifactPanelWidget
from ..widgets.event_timeline import EventTimelineWidget
from ..widgets.input_box import InputBoxWidget
from ..widgets.log_view import LogViewWidget
from ..widgets.plan_view import PlanViewWidget
from ..widgets.status_bar import StatusBar
from ..widgets.toast import ToastRack
from ..theme.colors import TEXT_SECONDARY
from ..widgets.task_detail_panels import (
    NotificationStripWidget,
    RemoteMCPAuthorizationWidget,
    SubagentActivityWidget,
    TaskHeaderWidget,
    TodoPanelWidget,
)


class TaskDetailScreen(Screen):  # type: ignore[misc]
    PANE_ORDER = ["timeline", "side"]

    def compose(self) -> ComposeResult:
        yield Container(
            StatusBar(id="status-bar"),
            TaskHeaderWidget(id="task-detail-header"),
            Horizontal(
                EventTimelineWidget(id="task-detail-timeline"),
                LogViewWidget(id="task-detail-logs", classes="-hidden"),
                Vertical(
                    PlanViewWidget(id="task-detail-plan"),
                    TodoPanelWidget(id="task-detail-todos"),
                    SubagentActivityWidget(id="task-detail-subagents"),
                    ArtifactPanelWidget(id="task-detail-artifacts"),
                    RemoteMCPAuthorizationWidget(id="task-detail-remote-mcp"),
                    NotificationStripWidget(id="task-detail-notifications"),
                    id="task-detail-side",
                ),
                id="task-detail-main",
            ),
            InputBoxWidget(id="task-detail-input"),
            Static(id="task-detail-footer"),
            ToastRack(id="toast-rack"),
            id="task-detail-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        root = self.query_one("#task-detail-root", Container)
        narrow = state.terminal_width < 100
        wide = state.terminal_width >= 140
        root.set_class(narrow, "-narrow")
        root.set_class(wide, "-wide")
        self.query_one(StatusBar).update_from_state(state)
        self.query_one(TaskHeaderWidget).update_header(selected_task_header(state))
        timeline_focused = state.focused_pane == "timeline"
        side_focused = state.focused_pane == "side"
        main = self.query_one("#task-detail-main", Horizontal)
        main.set_class(narrow, "-narrow")
        main.set_class(wide, "-wide")
        for split_class in ("-split-50-50", "-split-60-40", "-split-70-30"):
            main.remove_class(split_class)
        main.add_class(f"-split-{state.task_detail_split.replace('_', '-')}")
        timeline_widget = self.query_one(EventTimelineWidget)
        timeline_widget.set_class(state.task_detail_show_logs, "-hidden")
        timeline_widget.border_title = _pane_title(1, "Event Timeline", focused=timeline_focused)
        timeline_widget.update_timeline(task_timeline(state))
        log_view = self.query_one(LogViewWidget)
        log_view.border_title = _pane_title(1, "Logs", focused=timeline_focused)
        log_view.update_logs(
            task_logs(state),
            visible=state.task_detail_show_logs,
        )
        plan_panel = self.query_one(PlanViewWidget)
        todo_panel = self.query_one(TodoPanelWidget)
        subagents_panel = self.query_one(SubagentActivityWidget)
        artifacts_panel = self.query_one(ArtifactPanelWidget)
        remote_mcp_panel = self.query_one(RemoteMCPAuthorizationWidget)
        notifications_panel = self.query_one(NotificationStripWidget)
        task = state.task_snapshots.get(state.selected_task_id or "")
        panel_order = [plan_panel, todo_panel, subagents_panel, artifacts_panel, remote_mcp_panel, notifications_panel]
        if task is not None and bool(task.get("awaiting_approval")):
            panel_order = [notifications_panel, plan_panel, todo_panel, subagents_panel, artifacts_panel, remote_mcp_panel]
        elif task is not None and _has_active_subagent(task):
            panel_order = [subagents_panel, plan_panel, todo_panel, artifacts_panel, remote_mcp_panel, notifications_panel]
        side = self.query_one("#task-detail-side", Vertical)
        anchor = None
        for panel in panel_order:
            if anchor is None:
                side.move_child(panel, before=0)
            else:
                side.move_child(panel, after=anchor)
            anchor = panel
        for panel, title in [
            (plan_panel, "② Plan"),
            (todo_panel, "② Todos"),
            (subagents_panel, "② Subagent Activity"),
            (artifacts_panel, "② Artifacts"),
            (remote_mcp_panel, "② Remote MCP Auth"),
            (notifications_panel, "② Attention"),
        ]:
            panel.border_title = title
            panel.set_class(side_focused, "-focused-pane")
        plan_panel.update_plan(task_plan_view(state))
        todo_panel.update_todos(task_todo_view(state))
        subagents_panel.update_subagents(task_subagent_activity(state))
        artifacts_panel.update_artifacts(task_artifact_panel(state))
        remote_mcp_panel.update_authorizations(
            selected_remote_mcp_authorizations(state)
        )
        notifications_panel.update_notifications(task_notifications(state))
        self.query_one(InputBoxWidget).update_actions(task_action_bar(state))
        timeline_state = timeline_state_summary(state)
        footer = footer_hints(state, contextual=True)
        footer.append(
            f"\nTimeline filter: {escape(timeline_state.filter_label)}   "
            f"Search: {escape(timeline_state.search_query) if timeline_state.search_query else 'none'}",
            style=TEXT_SECONDARY,
        )
        self.query_one("#task-detail-footer", Static).update(footer)

    def on_key(self, event: Key) -> None:
        app = getattr(self, "app", None)
        store = getattr(app, "_store", None)
        if store is None:
            return
        state = store.snapshot()
        key = getattr(event, "key", "")
        if not state.task_detail_show_logs:
            timeline_view = self.query_one(EventTimelineWidget)
            if key == "g":
                timeline_view.scroll_to_home()
                event.stop()
            elif key in {"G", "shift+g"}:
                timeline_view.jump_to_latest()
                event.stop()
            return
        log_view = self.query_one(LogViewWidget)
        if key == "j":
            log_view.scroll_line(1)
            event.stop()
        elif key == "k":
            log_view.scroll_line(-1)
            event.stop()
        elif key == "g":
            log_view.scroll_to_home()
            event.stop()
        elif key in {"G", "shift+g"}:
            log_view.scroll_to_end()
            event.stop()


def _pane_title(number: int, title_text: str, *, focused: bool) -> str:
    glyph = {1: "①", 2: "②"}.get(number, str(number))
    return f"{glyph} {title_text}" if not focused else f"> {glyph} {title_text}"


def _has_active_subagent(task: dict[str, object]) -> bool:
    value = task.get("active_subagent")
    return isinstance(value, str) and bool(value.strip())
