from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
    task_timeline,
    timeline_state_summary,
)
from ..widgets.artifact_panel import ArtifactPanelWidget
from ..widgets.event_timeline import EventTimelineWidget
from ..widgets.input_box import InputBoxWidget
from ..widgets.log_view import LogViewWidget
from ..widgets.plan_view import PlanViewWidget
from ..widgets.status_bar import StatusBar
from ..widgets.task_detail_panels import (
    NotificationStripWidget,
    SubagentActivityWidget,
    TaskHeaderWidget,
)

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.screen import Screen
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container, Horizontal, Vertical
        from textual.screen import Screen
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        Horizontal = cast(Any, object)
        Vertical = cast(Any, object)
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
                    SubagentActivityWidget(id="task-detail-subagents"),
                    ArtifactPanelWidget(id="task-detail-artifacts"),
                    NotificationStripWidget(id="task-detail-notifications"),
                    id="task-detail-side",
                ),
                id="task-detail-main",
            ),
            InputBoxWidget(id="task-detail-input"),
            Static(id="task-detail-footer"),
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
        self.query_one(SubagentActivityWidget).update_subagents(task_subagent_activity(state))
        self.query_one(ArtifactPanelWidget).update_artifacts(task_artifact_panel(state))
        self.query_one(NotificationStripWidget).update_notifications(task_notifications(state))
        self.query_one(InputBoxWidget).update_actions(task_action_bar(state))
        timeline_state = timeline_state_summary(state)
        footer = "   ".join(footer_hints(state))
        footer = (
            f"{footer}\nTimeline filter: {timeline_state.filter_label}   "
            f"Search: {timeline_state.search_query or 'none'}"
        )
        self.query_one("#task-detail-footer", Static).update(footer)
