from __future__ import annotations

from typing import Any

from rich.markup import escape

from ..compat import Binding, ComposeResult, Container, ListView, Screen, Static, _TEXTUAL_IMPORT_ERROR
from ..store.app_state import AppState
from ..store.selectors import (
    config_profiles_summary,
    config_section_items,
    footer_hints,
    selected_config_detail,
)
from ..widgets.config_detail import ConfigDetailWidget
from ..widgets.config_section_list import ConfigSectionListWidget, ConfigSectionRow
from ..widgets.status_bar import StatusBar
from ..widgets.toast import ToastRack
from ..theme.colors import STATUS_DANGER, TEXT_SECONDARY


class ConfigScreen(Screen):  # type: ignore[misc]
    PANE_ORDER = ["config_sections"]
    BINDINGS = [Binding("c", "refresh_config", "Refresh", show=False, priority=True)]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_footer: str | None = None

    def compose(self) -> ComposeResult:
        yield Container(
            StatusBar(id="status-bar"),
            Container(
                ConfigSectionListWidget(id="config-screen-sections"),
                Container(
                    Static(id="config-screen-profiles"),
                    ConfigDetailWidget(id="config-screen-detail"),
                    id="config-screen-detail-column",
                ),
                id="config-screen-main",
            ),
            Static(id="config-screen-footer"),
            ToastRack(id="toast-rack"),
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
        self.query_one("#config-screen-profiles", Static).update(config_profiles_summary(state))
        detail_widget = self.query_one(ConfigDetailWidget)
        if state.config_request_status == "loading":
            detail_widget.show_loading("Refreshing configuration snapshot...")
        else:
            detail_model = selected_config_detail(state)
            detail_widget.update_detail(detail_model)
        footer = footer_hints(state, contextual=True)
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
