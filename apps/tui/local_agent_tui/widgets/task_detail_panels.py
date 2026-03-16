from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.selectors import (
    NotificationStripViewModel,
    SubagentActivityItemViewModel,
    TaskDetailHeaderViewModel,
)
from ..theme.colors import ACCENT, DANGER, SUCCESS, WARNING

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class TaskHeaderWidget(Static):  # type: ignore[misc]
    def update_header(self, model: TaskDetailHeaderViewModel | None) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Task Header"
        if model is None:
            self.update("No task selected.")
            return
        status = _status_markup(model.status)
        lines = [
            f"{model.task_id}  {status}  {model.run_id}",
            f"Created: {model.created_at}   Updated: {model.updated_at}",
            f"Phase: {model.current_phase}   Next: {model.actionable_label}",
        ]
        if model.active_subagent:
            lines[-1] = f"{lines[-1]}   Active: {model.active_subagent}"
        lines.append(f"Objective: {model.objective or 'No objective available.'}")
        lines.append(model.actionable_hint)
        self.update("\n".join(lines))


class SubagentActivityWidget(Static):  # type: ignore[misc]
    def update_subagents(self, items: list[SubagentActivityItemViewModel]) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Subagent Activity"
        if not items:
            self.update("No subagent activity yet.")
            return
        self.update(
            "\n".join(
                f"{item.subagent_id}  {_status_markup(item.status)}\n{item.latest_summary}"
                for item in items
            )
        )


class NotificationStripWidget(Static):  # type: ignore[misc]
    def update_notifications(self, model: NotificationStripViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Attention"
        if not model.items:
            self.update("No urgent updates.")
            return
        self.update(
            "\n".join(
                f"{item.timestamp} {_severity_markup(item.severity)} {item.summary}"
                for item in model.items
            )
        )


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


def _severity_markup(severity: str) -> str:
    color = {
        "error": DANGER,
        "attention": WARNING,
        "success": SUCCESS,
    }.get(severity.lower(), ACCENT)
    return f"[{color}][{severity.upper()}][/]"
