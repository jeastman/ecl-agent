from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.text import Text

from ..renderables import badge, block, join, metadata_line, muted, text
from ..store.selectors import (
    NotificationStripViewModel,
    SubagentActivityItemViewModel,
    TaskDetailHeaderViewModel,
)
from ..theme.colors import ACCENT, DANGER, SUCCESS, WARNING

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import VerticalScroll
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import VerticalScroll
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        VerticalScroll = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class TaskHeaderWidget(VerticalScroll):  # type: ignore[misc]
    can_focus = True

    def compose(self) -> ComposeResult:
        yield Static(id="task-detail-header-body")

    def update_header(self, model: TaskDetailHeaderViewModel | None) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Task Header"
        body = self.query_one("#task-detail-header-body", Static)
        if model is None:
            body.update("No task selected.")
            self.scroll_to(y=0, animate=False, immediate=True)
            return
        status_style = {
            "executing": ACCENT,
            "planning": ACCENT,
            "running": ACCENT,
            "completed": SUCCESS,
            "failed": DANGER,
            "paused": WARNING,
            "awaiting_approval": WARNING,
        }.get(model.status.lower(), ACCENT)
        meta_pairs = [
            ("Created", model.created_at),
            ("Updated", model.updated_at),
            ("Phase", model.current_phase),
            ("Next", model.actionable_label),
        ]
        if model.active_subagent:
            meta_pairs.append(("Active", model.active_subagent))
        body.update(
            block(
                [
                    join(
                        [
                            text(model.task_id, style="bold"),
                            badge(model.status.upper(), style=status_style),
                            muted(model.run_id),
                        ],
                        separator="  ",
                    ),
                    metadata_line(meta_pairs),
                    Text(""),
                    text("Objective", style="bold"),
                    text(model.objective or "No objective available."),
                    Text(""),
                    muted(model.actionable_hint),
                ]
            )
        )
        self.scroll_to(y=0, animate=False, immediate=True)

    def scroll_line(self, delta: int) -> None:
        next_y = max(0.0, min(self.max_scroll_y, self.scroll_y + delta))
        self.scroll_to(y=next_y, animate=False, immediate=True)

    def scroll_to_home(self) -> None:
        self.scroll_to(y=0, animate=False, immediate=True)

    def scroll_to_end(self) -> None:
        self.scroll_to(y=self.max_scroll_y, animate=False, immediate=True)


class SubagentActivityWidget(Static):  # type: ignore[misc]
    def update_subagents(self, items: list[SubagentActivityItemViewModel]) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Subagent Activity"
        if not items:
            self.update("No subagent activity yet.")
            return
        rows: list[Text] = []
        for item in items:
            status_style = {
                "running": ACCENT,
                "completed": SUCCESS,
                "failed": DANGER,
                "paused": WARNING,
            }.get(item.status.lower(), ACCENT)
            rows.append(
                join(
                    [
                        text(item.subagent_id, style="bold"),
                        badge(item.status.upper(), style=status_style),
                    ],
                    separator="  ",
                )
            )
            rows.append(text(item.latest_summary))
            if item.started_at or item.completed_at:
                pairs = []
                if item.started_at:
                    pairs.append(("Started", item.started_at))
                if item.completed_at:
                    pairs.append(("Completed", item.completed_at))
                rows.append(metadata_line(pairs))
            rows.append(Text(""))
        rows.pop()
        self.update(Group(*rows))


class NotificationStripWidget(Static):  # type: ignore[misc]
    def update_notifications(self, model: NotificationStripViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Attention"
        if not model.items:
            self.update("No urgent updates.")
            return
        self.update(Group(*(_render_notification_line(timestamp=item.timestamp, severity=item.severity, summary=item.summary) for item in model.items)))


def _render_notification_line(*, timestamp: str, severity: str, summary: str) -> Group:
    severity_style = {
        "error": DANGER,
        "attention": WARNING,
        "success": SUCCESS,
    }.get(severity.lower(), ACCENT)
    return block(
        [
            join([muted(timestamp), badge(severity.upper(), style=severity_style)], separator="  "),
            text(summary),
        ]
    )
