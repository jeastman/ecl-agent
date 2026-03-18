from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.text import Text

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
        super().__init__(Label(Text(f"{item.title}\n{item.subtitle}")))


class MemoryEntryListWidget(ListView):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_signature: tuple[tuple[tuple[str, bool], ...], bool] | None = None

    def update_entries(self, items: list[MemoryEntryItemViewModel], *, focused: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        signature = (
            tuple((item.memory_id, item.is_selected) for item in items),
            focused,
        )
        self.border_title = "Entries"
        self.border_subtitle = "Focused" if focused else ""
        self.set_class(focused, "-focused-pane")
        if self._last_signature == signature:
            return
        self.clear()
        selected_index = None
        for index, item in enumerate(items):
            self.append(MemoryEntryRow(item))
            if item.is_selected:
                selected_index = index
        if selected_index is not None:
            self.index = selected_index
        self._last_signature = signature
