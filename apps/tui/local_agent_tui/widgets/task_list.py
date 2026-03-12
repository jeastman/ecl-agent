from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.selectors import TaskListItemViewModel
from ..theme.colors import ACCENT, DANGER, SUCCESS, WARNING

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
        status_bits = [_status_markup(item.status)]
        if item.awaiting_approval:
            status_bits.append(f"[{WARNING}]APPROVAL[/]")
        if item.artifact_count:
            status_bits.append(f"[{ACCENT}]ART {item.artifact_count}[/]")
        text = f"{item.task_id}  {' | '.join(status_bits)}"
        if item.objective:
            text = f"{text}\n{item.objective}"
        if item.is_highlighted:
            text = f"[reverse]{text}[/reverse]"
        super().__init__(Label(text))


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


def _status_markup(status: str) -> str:
    color = {
        "executing": ACCENT,
        "planning": ACCENT,
        "completed": SUCCESS,
        "failed": DANGER,
        "paused": WARNING,
        "awaiting_approval": WARNING,
        "accepted": ACCENT,
    }.get(status.lower(), ACCENT)
    return f"[{color}]{status.upper()}[/]"
