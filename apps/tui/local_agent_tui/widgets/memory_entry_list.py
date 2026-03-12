from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.selectors import MemoryEntryItemViewModel

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


class MemoryEntryRow(ListItem):  # type: ignore[misc]
    def __init__(self, item: MemoryEntryItemViewModel) -> None:
        self.memory_id = item.memory_id
        super().__init__(Label(f"{item.title}\n{item.subtitle}"))


class MemoryEntryListWidget(ListView):  # type: ignore[misc]
    def update_entries(self, items: list[MemoryEntryItemViewModel], *, focused: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.clear()
        selected_index = None
        for index, item in enumerate(items):
            self.append(MemoryEntryRow(item))
            if item.is_selected:
                selected_index = index
        if selected_index is not None:
            self.index = selected_index
        self.border_title = "Entries"
        self.set_class(focused, "-focused-pane")
