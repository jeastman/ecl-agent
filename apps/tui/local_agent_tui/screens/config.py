from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import config_section_items, footer_hints, selected_config_detail
from ..widgets.config_detail import ConfigDetailWidget
from ..widgets.config_section_list import ConfigSectionListWidget, ConfigSectionRow
from ..widgets.status_bar import StatusBar
from ..theme.colors import STATUS_DANGER, TEXT_SECONDARY

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Container
    from textual.screen import Screen
    from textual.widgets import ListView, Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.binding import Binding
        from textual.containers import Container
        from textual.screen import Screen
        from textual.widgets import ListView, Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Binding = cast(Any, object)
        Container = cast(Any, object)
        Screen = cast(Any, object)
        ListView = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class ConfigScreen(Screen):  # type: ignore[misc]
    BINDINGS = [Binding("c", "refresh_config", "Refresh", show=False, priority=True)]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_footer: str | None = None

    def compose(self) -> ComposeResult:
        yield Container(
            StatusBar(id="status-bar"),
            Container(
                ConfigSectionListWidget(id="config-screen-sections"),
                ConfigDetailWidget(id="config-screen-detail"),
                id="config-screen-main",
            ),
            Static(id="config-screen-footer", markup=False),
            id="config-screen-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        self.query_one(ConfigSectionListWidget).update_sections(
            config_section_items(state),
            focused=state.focused_pane == "config_sections",
        )
        detail_model = selected_config_detail(state)
        self.query_one(ConfigDetailWidget).update_detail(detail_model)
        footer = footer_hints(state)
        footer.append("\nConfig viewer is read-only.", style=TEXT_SECONDARY)
        if state.config_request_error:
            footer.append(f"\n{escape(state.config_request_error)}", style=STATUS_DANGER)
        if self._last_footer != footer.plain:
            self.query_one("#config-screen-footer", Static).update(footer)
            self._last_footer = footer.plain

    def on_list_view_highlighted(self, message: ListView.Highlighted) -> None:
        if message.list_view.id != "config-screen-sections":
            return
        if isinstance(message.item, ConfigSectionRow):
            items = config_section_items(self.app._store.snapshot())  # type: ignore[attr-defined]
            index = getattr(message.list_view, "index", None)
            if not isinstance(index, int) or index < 0 or index >= len(items):
                return
            if items[index].section_id != message.item.section_id:
                return
            self.app.handle_config_section_selected(message.item.section_id)  # type: ignore[attr-defined]

    def action_refresh_config(self) -> None:
        self.app.action_open_config()  # type: ignore[attr-defined]
