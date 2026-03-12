from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import config_section_items, footer_hints, selected_config_detail
from ..widgets.config_detail import ConfigDetailWidget
from ..widgets.config_section_list import ConfigSectionListWidget, ConfigSectionRow

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.screen import Screen
    from textual.widgets import ListView, Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container
        from textual.screen import Screen
        from textual.widgets import ListView, Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        Screen = cast(Any, object)
        ListView = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class ConfigScreen(Screen):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            Container(
                ConfigSectionListWidget(id="config-screen-sections"),
                ConfigDetailWidget(id="config-screen-detail"),
                id="config-screen-main",
            ),
            Static(id="config-screen-footer"),
            id="config-screen-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(ConfigSectionListWidget).update_sections(
            config_section_items(state),
            focused=state.focused_pane == "config_sections",
        )
        detail_model = selected_config_detail(state)
        self.query_one(ConfigDetailWidget).update_detail(detail_model)
        footer = "   ".join(footer_hints(state))
        footer = f"{footer}\nConfig viewer is read-only."
        if state.config_request_error:
            footer = f"{footer}\n{state.config_request_error}"
        self.query_one("#config-screen-footer", Static).update(footer)

    def on_list_view_highlighted(self, message: ListView.Highlighted) -> None:
        if message.list_view.id != "config-screen-sections":
            return
        if isinstance(message.item, ConfigSectionRow):
            self.app.handle_config_section_selected(message.item.section_id)  # type: ignore[attr-defined]
