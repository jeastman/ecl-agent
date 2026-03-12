from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import diagnostics_items, footer_hints, selected_diagnostics_detail
from ..widgets.status_bar import StatusBar

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
            id="diagnostics-screen-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        items = diagnostics_items(state)
        list_panel = self.query_one("#diagnostics-screen-list", Static)
        list_panel.border_title = "Diagnostics"
        list_panel.update(
            "\n".join(
                (
                    "\n".join(
                        [
                            f"{'>' if item.is_selected else ' '} {item.kind}  {item.created_at}",
                            f"  {item.message}",
                        ]
                    )
                )
                for item in items
            )
            or "No diagnostics."
        )
        detail = selected_diagnostics_detail(state)
        detail_panel = self.query_one("#diagnostics-screen-detail", Static)
        detail_panel.border_title = detail.title
        detail_panel.update(f"{detail.summary}\n\n{detail.body}".strip())
        self.query_one("#diagnostics-screen-footer", Static).update("   ".join(footer_hints(state)))
