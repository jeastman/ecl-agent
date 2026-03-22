from __future__ import annotations

from typing import Any

from rich.text import Text

from ..compat import Label, ListItem, ListView, _TEXTUAL_IMPORT_ERROR
from ..store.selectors import ConfigSectionItemViewModel
from ..theme.colors import ACCENT, TEXT_MUTED_DEEP, TEXT_SECONDARY


class ConfigSectionRow(ListItem):  # type: ignore[misc]
    def __init__(self, item: ConfigSectionItemViewModel) -> None:
        self.section_id = item.section_id
        self._label = Label(classes="config-section-row-content")
        super().__init__(self._label)
        self.update_item(item)

    def update_item(self, item: ConfigSectionItemViewModel) -> None:
        self.section_id = item.section_id
        text = Text()
        text.append("▎ " if item.is_selected else "  ", style=ACCENT if item.is_selected else TEXT_MUTED_DEEP)
        text.append(f"{item.icon} ", style="bold")
        text.append(item.title, style="bold" if item.is_selected else "")
        text.append("\n")
        text.append("   ")
        text.append(item.description, style=TEXT_SECONDARY)
        text.no_wrap = False
        self._label.update(text)
        self.set_class(item.is_selected, "-selected")


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
