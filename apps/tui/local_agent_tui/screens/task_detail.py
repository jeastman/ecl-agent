from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.markup import escape

from ..store.app_state import AppState
from ..store.selectors import (
    footer_hints,
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
    SubagentActivityWidget,
    TaskHeaderWidget,
    TodoPanelWidget,
)

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.screen import Screen
    from textual.events import Key
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container, Horizontal, Vertical
        from textual.events import Key
        from textual.screen import Screen
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        Horizontal = cast(Any, object)
        Vertical = cast(Any, object)
        Key = cast(Any, object)
        Screen = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class TaskDetailScreen(Screen):  # type: ignore[misc]
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
        self.query_one(StatusBar).update_from_state(state)
        self.query_one(TaskHeaderWidget).update_header(selected_task_header(state))
        timeline_widget = self.query_one(EventTimelineWidget)
        timeline_widget.set_class(state.task_detail_show_logs, "-hidden")
        timeline_widget.update_timeline(task_timeline(state))
        self.query_one(LogViewWidget).update_logs(
            task_logs(state),
            visible=state.task_detail_show_logs,
        )
        self.query_one(PlanViewWidget).update_plan(task_plan_view(state))
        self.query_one(TodoPanelWidget).update_todos(task_todo_view(state))
        self.query_one(SubagentActivityWidget).update_subagents(task_subagent_activity(state))
        self.query_one(ArtifactPanelWidget).update_artifacts(task_artifact_panel(state))
        self.query_one(NotificationStripWidget).update_notifications(task_notifications(state))
        self.query_one(InputBoxWidget).update_actions(task_action_bar(state))
        timeline_state = timeline_state_summary(state)
        footer = footer_hints(state)
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
