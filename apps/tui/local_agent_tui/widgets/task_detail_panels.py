from __future__ import annotations

from rich.console import Group
from rich.markup import escape
from rich.text import Text

from ..compat import ComposeResult, Static, VerticalScroll, _TEXTUAL_IMPORT_ERROR
from ..renderables import badge, block, divider, join, metadata_line, muted, text
from ..store.selectors import (
    NotificationStripViewModel,
    RemoteMCPAuthorizationViewModel,
    SubagentActivityItemViewModel,
    TaskDetailHeaderViewModel,
    TodoPanelViewModel,
)
from ..theme.colors import ACCENT, DANGER, SUCCESS, TEXT_MUTED_DEEP, TEXT_PRIMARY, TEXT_SECONDARY, WARNING
from ..theme.empty_states import render_empty_state
from ..theme.typography import label, muted, status_badge, title, value
from ..utils.text import truncate, truncate_id
from ._dirty import DirtyCheckMixin


class TaskHeaderWidget(DirtyCheckMixin, VerticalScroll):  # type: ignore[misc]
    can_focus = True

    def compose(self) -> ComposeResult:
        yield Static(id="task-detail-header-body")

    def update_header(self, model: TaskDetailHeaderViewModel | None) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Task Header"
        if not self._should_render(model):
            return
        body = self.query_one("#task-detail-header-body", Static)
        if model is None:
            body.update("No task selected.")
            return

        heading = Text()
        heading.append_text(title(truncate_id(model.task_id, width=28)))
        heading.append("  ")
        heading.append_text(status_badge(model.status))
        heading.append("  ")
        heading.append_text(label("Phase: "))
        heading.append_text(value(model.current_phase))
        if model.active_subagent:
            heading.append("  ")
            heading.append_text(label("Active: "))
            heading.append_text(value(truncate(model.active_subagent, 16)))
        if model.run_id:
            heading.append("  ")
            heading.append_text(muted(f"\N{BLACK RIGHT-POINTING SMALL TRIANGLE} {truncate_id(model.run_id, width=20)}"))

        objective = Text()
        objective.append_text(label("Objective: "))
        objective.append_text(value(truncate(model.objective or "No objective available.", 120)))
        body.update(Text("\n").join([heading, objective]))


class SubagentActivityWidget(DirtyCheckMixin, Static):  # type: ignore[misc]
    def update_subagents(self, items: list[SubagentActivityItemViewModel]) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Subagent Activity"
        if not self._should_render(items):
            return
        if not items:
            self.update(render_empty_state("subagents"))
            return
        lines: list[Text] = []
        for item in items:
            line = Text()
            line.append(f"{item.status_icon} ", style=_status_style(item.status))
            line.append(truncate(item.subagent_id, 20), style="bold")
            line.append("  ")
            line.append_text(status_badge(item.status))
            line.append("  ")
            line.append(truncate(item.latest_summary, 56), style=TEXT_SECONDARY)
            lines.append(line)
        self.update(Text("\n").join(lines))


class TodoPanelWidget(DirtyCheckMixin, Static):  # type: ignore[misc]
    def update_todos(self, model: TodoPanelViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Todos"
        if not self._should_render(model):
            return
        if not model.items:
            self.update(render_empty_state("todos"))
            return
        lines: list[Text] = []
        summary = Text()
        summary.append(f"◉ {model.in_progress_count}", style=ACCENT)
        summary.append("  ")
        summary.append(f"○ {model.pending_count}", style=TEXT_SECONDARY)
        summary.append("  ")
        summary.append(f"✓ {model.completed_count}", style=SUCCESS)
        lines.append(summary)
        lines.append(divider(self.content_size.width - 2, style=TEXT_SECONDARY))
        for item in model.items:
            lines.append(_render_todo_line(item.status_icon, item.content, item.status))
        self.update(Text("\n").join(lines))


class NotificationStripWidget(DirtyCheckMixin, Static):  # type: ignore[misc]
    def update_notifications(self, model: NotificationStripViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Attention"
        if not self._should_render(model):
            return
        if not model.items:
            self.set_class(False, "-urgent-pane")
            self.update(render_empty_state("notifications"))
            return
        self.set_class(any(item.tone in {"warning", "danger"} for item in model.items), "-urgent-pane")
        self.update(
            Text("\n").join(
                [
                    _render_notification_line(
                        timestamp=item.timestamp,
                        timestamp_relative=item.timestamp_relative,
                        severity=item.severity,
                        summary=item.summary,
                        icon=item.icon,
                        tone=item.tone,
                    )
                    for item in model.items
                ]
            )
        )


class RemoteMCPAuthorizationWidget(DirtyCheckMixin, Static):  # type: ignore[misc]
    def update_authorizations(self, items: list[RemoteMCPAuthorizationViewModel]) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Remote MCP Auth"
        if not self._should_render(items):
            return
        if not items:
            self.update(render_empty_state("notifications"))
            return
        lines: list[Text] = []
        for item in items:
            line = Text()
            line.append("🔐 ", style=WARNING)
            line.append(f"{item.server_name}", style="bold")
            line.append("  ")
            line.append_text(status_badge(item.status.upper()))
            lines.append(line)
            lines.append(Text(item.summary, style=TEXT_SECONDARY))
            if item.actions:
                action_line = Text("Actions: ", style=TEXT_MUTED_DEEP)
                action_line.append(", ".join(action.title for action in item.actions), style=TEXT_PRIMARY)
                lines.append(action_line)
            lines.append(Text(""))
        self.update(Group(*lines[:-1] if lines and not lines[-1].plain.strip() else lines))


def _render_notification_line(*, timestamp: str, severity: str, summary: str) -> Group:
    severity_style = {
        "error": DANGER,
        "attention": WARNING,
        "success": SUCCESS,
    }.get(severity.lower(), ACCENT)
    return f"[{color}]\\[{escape(severity.upper())}\\][/]"


def _status_style(status: str) -> str:
    return {
        "running": ACCENT,
        "executing": ACCENT,
        "planning": ACCENT,
        "completed": SUCCESS,
        "cancelled": WARNING,
        "failed": DANGER,
        "paused": WARNING,
        "awaiting_approval": WARNING,
    }.get(status.lower(), TEXT_SECONDARY)


def _todo_status_style(status: str) -> str:
    return {
        "in_progress": ACCENT,
        "pending": TEXT_SECONDARY,
        "completed": SUCCESS,
    }.get(status.lower(), TEXT_SECONDARY)


def _todo_content_style(status: str) -> str:
    return {
        "in_progress": "bold",
        "pending": "none",
        "completed": TEXT_MUTED_DEEP,
    }.get(status.lower(), "none")


def _render_todo_line(icon: str, content: str, status: str) -> Text:
    line = Text()
    line.append(f"{icon} ", style=_todo_status_style(status))
    line.append(content, style=_todo_content_style(status))
    return line


def _notification_tone_style(tone: str) -> str:
    return {
        "warning": WARNING,
        "danger": DANGER,
        "success": SUCCESS,
        "info": ACCENT,
    }.get(tone, TEXT_SECONDARY)


def _render_notification_line(
    *,
    timestamp: str,
    timestamp_relative: str,
    severity: str,
    summary: str,
    icon: str,
    tone: str,
) -> Text:
    del timestamp, severity
    line = Text()
    line.append("▐ ", style=_notification_tone_style(tone))
    line.append(f"{icon} ", style=_notification_tone_style(tone))
    line.append(summary)
    line.append("  ")
    line.append(timestamp_relative, style=TEXT_MUTED_DEEP)
    return line
