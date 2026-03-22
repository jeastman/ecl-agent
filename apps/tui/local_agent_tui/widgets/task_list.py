from __future__ import annotations

import re
from typing import Any

from rich.cells import cell_len
from rich.console import Group
from rich.text import Text

from ..compat import Label, ListItem, ListView, _TEXTUAL_IMPORT_ERROR
from ..store.selectors import TaskListItemViewModel
from ..theme.empty_states import render_empty_state
from ..theme.colors import ACCENT, DANGER, SUCCESS, TEXT_MUTED, TEXT_MUTED_DEEP, WARNING
from ..theme.typography import status_badge
from ..utils.time_format import relative_time
from ..utils.text import truncate
from ..utils.text import truncate_id
from ._dirty import DirtyCheckMixin


class TaskListRow(ListItem):  # type: ignore[misc]
    def __init__(self, item: TaskListItemViewModel) -> None:
        self.task_id = item.task_id
        self.run_id = item.run_id
        self._item = item
        self._compact = False
        self._label = Label(classes="task-list-row-content")
        super().__init__(self._label, classes="task-list-row")
        self.update_item(item, compact=False, pulse_on=True)

    def update_item(
        self,
        item: TaskListItemViewModel,
        compact: bool,
        width: int | None = None,
        *,
        pulse_on: bool,
    ) -> None:
        self.task_id = item.task_id
        self.run_id = item.run_id
        self._item = item
        self._compact = compact
        self._label.update(_row_content(item, compact=compact, width=width, pulse_on=pulse_on))
        self.set_class(compact, "-compact")

    def refresh_pulse(self, pulse_on: bool, width: int | None = None) -> None:
        self._label.update(
            _row_content(self._item, compact=self._compact, width=width, pulse_on=pulse_on)
        )


class TaskListEmptyRow(ListItem):  # type: ignore[misc]
    can_focus = False

    def __init__(self) -> None:
        super().__init__(Label(render_empty_state("tasks"), classes="task-list-row-content"), classes="task-list-row task-list-empty-row")


class TaskListPlaceholderRow(ListItem):  # type: ignore[misc]
    can_focus = False

    def __init__(self, label: str) -> None:
        super().__init__(Label(Text(label), classes="task-list-row-content"), classes="task-list-row task-list-empty-row")


class TaskListWidget(DirtyCheckMixin, ListView):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._task_id_list: list[str] = []
        self._pulse_on = True
        self._pulse_timer = None

    def update_tasks(self, items: list[TaskListItemViewModel], *, focused: bool, compact: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        if list(self.query(TaskListEmptyRow)) or list(self.query(TaskListPlaceholderRow)):
            self.clear()
        elif items and not list(self.query(TaskListRow)):
            self._render_rows(items, focused=focused, compact=compact)
            return
        if not items:
            self.clear()
            self.append(TaskListEmptyRow())
            self._task_id_list = []
            self.index = None
            self.border_title = "Tasks"
            self.border_subtitle = "Focused" if focused else ""
            self.set_class(focused, "-focused-pane")
            return
        self._render_rows(items, focused=focused, compact=compact)

    def _toggle_pulse(self) -> None:  # pragma: no cover
        rows = list(self.query(TaskListRow))
        if not rows:
            return
        self._pulse_on = not self._pulse_on
        for row in rows:
            row.refresh_pulse(self._pulse_on, self.content_size.width)

    def _render_rows(
        self,
        items: list[TaskListItemViewModel],
        *,
        focused: bool,
        compact: bool,
    ) -> None:
        new_task_ids = [item.task_id for item in items]
        selected_index = None
        existing_rows = [row for row in self.query(TaskListRow)]
        while len(existing_rows) < len(items):
            row = TaskListRow(items[len(existing_rows)])
            self.append(row)
            existing_rows.append(row)
        for extra_row in existing_rows[len(items):]:
            extra_row.remove()
        existing_rows = existing_rows[: len(items)]
        for index, item in enumerate(items):
            existing_rows[index].update_item(
                item,
                compact,
                self.content_size.width,
                pulse_on=self._pulse_on,
            )
            if item.is_selected:
                selected_index = index
        self._task_id_list = new_task_ids
        self.index = selected_index
        self.border_title = "Tasks"
        self.border_subtitle = "Focused" if focused else ""
        self.set_class(focused, "-focused-pane")
        if any(item.is_live for item in items):
            if self._pulse_timer is None:
                self._pulse_timer = self.set_interval(1.0, self._toggle_pulse)
        elif self._pulse_timer is not None:
            self._pulse_timer.stop()
            self._pulse_timer = None
            self._pulse_on = True

    def show_loading(self, label: str, *, focused: bool) -> None:
        self._reset_render_cache()
        self.clear()
        self.append(TaskListPlaceholderRow(label))
        self._task_id_list = []
        self.index = None
        self.border_title = "Tasks"
        self.border_subtitle = "Focused" if focused else ""
        self.set_class(focused, "-focused-pane")


def _status_text(status: str) -> Text:
    color = _status_color(status)
    return Text(status.upper(), style=color)


def _row_content(
    item: TaskListItemViewModel,
    *,
    compact: bool,
    width: int | None = None,
    pulse_on: bool,
) -> Text:
    if compact:
        return _compact_row_content(item, width=width, pulse_on=pulse_on)

    lines: list[Text] = []

    top = Text()
    top.append(_selection_glyph(item))
    top.append(" ")
    top.append(_status_symbol(item.status, item.is_live, pulse_on), style=_status_color(item.status))
    top.append(" ")
    top.append(truncate(_objective_preview(item.objective), 48), style="bold")
    top.no_wrap = True
    top.append("   ")
    top.append(relative_time(item.updated_at), style=TEXT_MUTED)
    if item.unread_event_count > 0:
        top.append("  ")
        top.append(f"(+{item.unread_event_count})", style=TEXT_MUTED)
    if item.artifact_count:
        top.append("  ")
        top.append(f" {item.artifact_count} ", style=f"bold black on {ACCENT}")
    lines.append(top)

    bottom = Text()
    bottom.append("   ")
    bottom.append(truncate_id(item.task_id, width=18), style=TEXT_MUTED_DEEP)
    if item.run_id:
        bottom.append(" · ", style=TEXT_MUTED_DEEP)
        bottom.append(truncate_id(item.run_id, width=18), style=TEXT_MUTED_DEEP)
    if item.awaiting_approval:
        bottom.append(" · ", style=TEXT_MUTED_DEEP)
        bottom.append("approval", style=WARNING)
    bottom.no_wrap = True
    lines.append(bottom)
    return Text("\n").join(lines)


def _compact_row_content(
    item: TaskListItemViewModel,
    *,
    width: int | None = None,
    pulse_on: bool,
) -> Text:
    top = Text()
    top_prefix = f"{_selection_glyph(item)} {_status_symbol(item.status, item.is_live, pulse_on)} "
    top.append(_selection_glyph(item))
    top.append(" ")
    top.append(_status_symbol(item.status, item.is_live, pulse_on), style=_status_color(item.status))
    top.append(" ")
    available_width = max(10, (width or 36) - cell_len(top_prefix) - 2)
    top.append(truncate(_objective_preview(item.objective), available_width), style="bold")
    top.no_wrap = True

    bottom = Text()
    bottom.append("   ")
    bottom.append(relative_time(item.updated_at), style=TEXT_MUTED)
    if item.unread_event_count > 0:
        bottom.append("  ")
        bottom.append(f"(+{item.unread_event_count})", style=TEXT_MUTED)
    if item.awaiting_approval:
        bottom.append("  ")
        bottom.append("approval", style=WARNING)
    if item.artifact_count:
        bottom.append("  ")
        bottom.append(f" {item.artifact_count} ", style=f"bold black on {ACCENT}")
    bottom.no_wrap = True
    return Text("\n").join([top, bottom])


def _status_dot(status: str) -> Text:
    return Text("●", style=_status_color(status))


def _status_symbol(status: str, is_live: bool, pulse_on: bool) -> str:
    if is_live:
        return "●" if pulse_on else "◉"
    return {
        "completed": "✓",
        "cancelled": "■",
        "failed": "✗",
        "paused": "⏸",
        "awaiting_approval": "⚠",
        "accepted": "●",
    }.get(status.lower(), "●")


def _selection_glyph(item: TaskListItemViewModel) -> str:
    if item.is_selected:
        return "▎"
    if item.is_highlighted:
        return "•"
    return " "


def _status_color(status: str) -> str:
    return {
        "executing": ACCENT,
        "planning": ACCENT,
        "completed": SUCCESS,
        "cancelled": WARNING,
        "failed": DANGER,
        "paused": WARNING,
        "awaiting_approval": WARNING,
        "accepted": ACCENT,
    }.get(status.lower(), ACCENT)


def _objective_preview(objective: str) -> str:
    normalized = re.sub(r"[*_`>#-]+", " ", objective)
    normalized = " ".join(normalized.split())
    normalized = re.sub(r"^OBJECTIVE\s+", "", normalized, flags=re.IGNORECASE)
    if not normalized:
        return "No objective provided."
    if len(normalized) <= 84:
        return normalized
    return f"{normalized[:81].rstrip()}..."
