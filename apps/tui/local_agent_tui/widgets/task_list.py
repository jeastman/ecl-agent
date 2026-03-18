from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text

from ..store.selectors import TaskListItemViewModel
from ..theme.colors import ACCENT, DANGER, SUCCESS, TEXT_MUTED, WARNING

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.widgets import Label, ListItem, ListView
else:  # pragma: no cover
    try:
        from textual.widgets import Label, ListItem, ListView
    except ModuleNotFoundError as exc:
        Label = cast(Any, object)
        ListItem = cast(Any, object)
        ListView = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class TaskListRow(ListItem):  # type: ignore[misc]
    def __init__(self, item: TaskListItemViewModel) -> None:
        self.task_id = item.task_id
        self.run_id = item.run_id
        content = Text()
        if item.is_highlighted:
            content.stylize("reverse")
        content.append(_compact_id(item.task_id))
        content.append("  ")
        content.append_text(_status_text(item.status))
        if item.awaiting_approval:
            content.append(" | ")
            content.append("APPROVAL", style=WARNING)
        if item.artifact_count:
            content.append(" | ")
            content.append(f"ART {item.artifact_count}", style=ACCENT)
        content.append("\n")
        content.append(_objective_preview(item.objective))
        content.append("\n")
        content.append(
            f"Updated {_compact_timestamp(item.updated_at)}   {_compact_id(item.run_id)}",
            style=TEXT_MUTED,
        )
        super().__init__(Label(content, classes="task-list-row-content"), classes="task-list-row")


class TaskListWidget(ListView):  # type: ignore[misc]
    def update_tasks(self, items: list[TaskListItemViewModel], *, focused: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.clear()
        selected_index = None
        for index, item in enumerate(items):
            self.append(TaskListRow(item))
            if item.is_selected:
                selected_index = index
        if selected_index is not None:
            self.index = selected_index
        self.border_title = "Tasks"
        self.border_subtitle = "Focused" if focused else ""
        self.set_class(focused, "-focused-pane")


def _status_text(status: str) -> Text:
    color = {
        "executing": ACCENT,
        "planning": ACCENT,
        "completed": SUCCESS,
        "failed": DANGER,
        "paused": WARNING,
        "awaiting_approval": WARNING,
        "accepted": ACCENT,
    }.get(status.lower(), ACCENT)
    return Text(status.upper(), style=color)


def _objective_preview(objective: str) -> str:
    normalized = re.sub(r"[*_`>#-]+", " ", objective)
    normalized = " ".join(normalized.split())
    if not normalized:
        return "No objective provided."
    if len(normalized) <= 84:
        return normalized
    return f"{normalized[:81].rstrip()}..."


def _compact_timestamp(timestamp: str) -> str:
    if "T" not in timestamp:
        return timestamp or "unknown"
    date_part, time_part = timestamp.split("T", 1)
    return f"{date_part} {time_part[:5]}"


def _compact_id(value: str) -> str:
    if len(value) <= 18:
        return value
    prefix, separator, remainder = value.partition("_")
    if not separator:
        return f"{value[:8]}...{value[-4:]}"
    return f"{prefix}_{remainder[:6]}...{remainder[-4:]}"
