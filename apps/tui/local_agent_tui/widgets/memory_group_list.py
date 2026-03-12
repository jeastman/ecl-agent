from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.selectors import MemoryGroupItemViewModel

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


class MemoryGroupRow(ListItem):  # type: ignore[misc]
    def __init__(self, item: MemoryGroupItemViewModel) -> None:
        self.group_id = item.group_id
        text = f"{item.title} ({item.count})\n{item.description}"
        super().__init__(Label(text))


class MemoryGroupListWidget(ListView):  # type: ignore[misc]
    def update_groups(self, items: list[MemoryGroupItemViewModel], *, focused: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.clear()
        selected_index = None
        for index, item in enumerate(items):
            self.append(MemoryGroupRow(item))
            if item.is_selected:
                selected_index = index
        if selected_index is not None:
            self.index = selected_index
        self.border_title = "Memory Scopes"
        self.set_class(focused, "-focused-pane")
