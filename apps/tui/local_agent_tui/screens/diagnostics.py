from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.text import Text

from ..store.app_state import AppState
from ..store.selectors import diagnostics_items, footer_hints, selected_diagnostics_detail
from ..widgets.loading import loading_renderable
from ..widgets.status_bar import StatusBar
from ..widgets.toast import ToastRack

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.screen import Screen
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container
        from textual.screen import Screen
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        Screen = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class DiagnosticsScreen(Screen):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            StatusBar(id="status-bar"),
            Container(
                Static(id="diagnostics-screen-list"),
                Static(id="diagnostics-screen-detail"),
                id="diagnostics-screen-main",
            ),
            Static(id="diagnostics-screen-footer"),
            ToastRack(id="toast-rack"),
            id="diagnostics-screen-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        if state.diagnostics_request_status == "loading":
            list_panel = self.query_one("#diagnostics-screen-list", Static)
            list_panel.border_title = "Diagnostics"
            list_panel.update(loading_renderable("Loading diagnostics...", skeleton_lines=4))
            detail_panel = self.query_one("#diagnostics-screen-detail", Static)
            detail_panel.border_title = "Diagnostics"
            detail_panel.update(loading_renderable("Loading diagnostic details...", skeleton_lines=5))
            self.query_one("#diagnostics-screen-footer", Static).update(footer_hints(state))
            return
        items = diagnostics_items(state)
        list_panel = self.query_one("#diagnostics-screen-list", Static)
        list_panel.border_title = "Diagnostics"
        if items:
            list_panel.update(Group(*(_render_diagnostic_list_item(item) for item in items)))
        else:
            list_panel.update("No diagnostics.")
        detail = selected_diagnostics_detail(state)
        detail_panel = self.query_one("#diagnostics-screen-detail", Static)
        detail_panel.border_title = detail.title
        detail_panel.update(_render_diagnostic_detail(detail.title, detail.summary, detail.body))
        self.query_one("#diagnostics-screen-footer", Static).update(footer_hints(state))


def _render_diagnostic_list_item(item: Any) -> Text:
    rendered = Text()
    rendered.append(f"{'>' if item.is_selected else ' '} {item.kind}  {item.created_at}")
    rendered.append("\n")
    rendered.append(f"  {item.message}")
    return rendered


def _render_diagnostic_detail(title: str, summary: str, body: str) -> Group:
    return Group(Text(summary), Text(""), Text(body))
