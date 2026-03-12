from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.selectors import ConfigSectionItemViewModel

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


class ConfigSectionRow(ListItem):  # type: ignore[misc]
    def __init__(self, item: ConfigSectionItemViewModel) -> None:
        self.section_id = item.section_id
        super().__init__(Label(f"{item.title}\n{item.description}"))


class ConfigSectionListWidget(ListView):  # type: ignore[misc]
    def update_sections(self, items: list[ConfigSectionItemViewModel], *, focused: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.clear()
        selected_index = None
        for index, item in enumerate(items):
            self.append(ConfigSectionRow(item))
            if item.is_selected:
                selected_index = index
        if selected_index is not None:
            self.index = selected_index
        self.border_title = "Config Sections"
        self.set_class(focused, "-focused-pane")
