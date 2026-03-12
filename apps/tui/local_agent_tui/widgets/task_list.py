from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.selectors import TaskListItemViewModel

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
        status_bits = [item.status.upper()]
        if item.awaiting_approval:
            status_bits.append("APPROVAL")
        if item.artifact_count:
            status_bits.append(f"ART {item.artifact_count}")
        text = f"{item.task_id}  {' | '.join(status_bits)}"
        if item.objective:
            text = f"{text}\n{item.objective}"
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
        self.set_class(focused, "-focused-pane")
