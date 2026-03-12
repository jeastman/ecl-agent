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
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_signature: tuple[tuple[tuple[str, bool], ...], bool] | None = None

    def update_sections(self, items: list[ConfigSectionItemViewModel], *, focused: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        signature = (
            tuple((item.section_id, item.is_selected) for item in items),
            focused,
        )
        self.border_title = "Config Sections"
        self.border_subtitle = "Focused" if focused else ""
        self.set_class(focused, "-focused-pane")
        if self._last_signature == signature:
            return
        self.clear()
        selected_index = None
        for index, item in enumerate(items):
            self.append(ConfigSectionRow(item))
            if item.is_selected:
                selected_index = index
        if selected_index is not None:
            self.index = selected_index
        self._last_signature = signature
