from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text

from ..store.selectors import TaskListItemViewModel
from ..theme.empty_states import render_empty_state
from ..theme.colors import ACCENT, DANGER, SUCCESS, TEXT_MUTED, WARNING
from ..theme.typography import status_badge
from ..utils.time_format import relative_time
from ..utils.text import truncate_id

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
        self._label = Label(classes="task-list-row-content")
        super().__init__(self._label, classes="task-list-row")
        self.update_item(item)

    def update_item(self, item: TaskListItemViewModel) -> None:
        self.task_id = item.task_id
        self.run_id = item.run_id
        self._label.update(_row_content(item))


class TaskListEmptyRow(ListItem):  # type: ignore[misc]
    can_focus = False

    def __init__(self) -> None:
        super().__init__(Label(render_empty_state("tasks"), classes="task-list-row-content"), classes="task-list-row task-list-empty-row")


class TaskListWidget(ListView):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._task_id_list: list[str] = []

    def update_tasks(self, items: list[TaskListItemViewModel], *, focused: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        if not items:
            self.clear()
            self.append(TaskListEmptyRow())
            self._task_id_list = []
            self.index = None
            self.border_title = "Tasks"
            self.border_subtitle = "Focused" if focused else ""
            self.set_class(focused, "-focused-pane")
            return
        new_task_ids = [item.task_id for item in items]
        selected_index = None
        if self._task_id_list == new_task_ids:
            existing_rows = [row for row in self.query(TaskListRow)]
            for index, item in enumerate(items):
                existing_rows[index].update_item(item)
                if item.is_selected:
                    selected_index = index
        else:
            self.clear()
            for index, item in enumerate(items):
                self.append(TaskListRow(item))
                if item.is_selected:
                    selected_index = index
            self._task_id_list = new_task_ids
        if selected_index is not None:
            self.index = selected_index
        elif not items:
            self.index = None
        self.border_title = "Tasks"
        self.border_subtitle = "Focused" if focused else ""
        self.set_class(focused, "-focused-pane")


def _status_text(status: str) -> Text:
    color = _status_color(status)
    return Text(status.upper(), style=color)


def _row_content(item: TaskListItemViewModel) -> Text:
    content = Text()
    content.append(_status_dot(item.status))
    content.append(" ")
    content.append(truncate_id(item.task_id, width=18), style="bold")
    content.append(" ")
    content.append_text(status_badge(item.status))
    if item.awaiting_approval:
        content.append(" ")
        content.append(" APPROVAL ", style=f"bold {WARNING}")
    if item.artifact_count:
        content.append(" ")
        content.append(f" ART {item.artifact_count} ", style=f"bold {ACCENT}")
    content.append("\n")
    content.append(_objective_preview(item.objective))
    content.append("\n")
    content.append("Updated ", style=TEXT_MUTED)
    content.append(relative_time(item.updated_at), style=TEXT_MUTED)
    content.append("   ", style=TEXT_MUTED)
    content.append(truncate_id(item.run_id, width=18), style=TEXT_MUTED)
    if item.is_highlighted:
        content.stylize("reverse")
    return content


def _status_dot(status: str) -> Text:
    return Text("●", style=_status_color(status))


def _status_color(status: str) -> str:
    return {
        "executing": ACCENT,
        "planning": ACCENT,
        "completed": SUCCESS,
        "failed": DANGER,
        "paused": WARNING,
        "awaiting_approval": WARNING,
        "accepted": ACCENT,
    }.get(status.lower(), ACCENT)


def _objective_preview(objective: str) -> str:
    normalized = re.sub(r"[*_`>#-]+", " ", objective)
    normalized = " ".join(normalized.split())
    if not normalized:
        return "No objective provided."
    if len(normalized) <= 84:
        return normalized
    return f"{normalized[:81].rstrip()}..."
