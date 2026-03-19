from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import selected_markdown_artifact
from ..widgets.status_bar import StatusBar
from ..widgets.markdown_viewer import MarkdownSearchState, MarkdownViewerWidget
from ..widgets.toast import ToastRack

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal
    from textual.screen import Screen
    from textual.widgets import Input, Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.binding import Binding
        from textual.containers import Container, Horizontal
        from textual.screen import Screen
        from textual.widgets import Input, Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Binding = cast(Any, object)
        Container = cast(Any, object)
        Horizontal = cast(Any, object)
        Screen = cast(Any, object)
        Input = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class MarkdownViewerScreen(Screen):  # type: ignore[misc]
    BINDINGS = [
        Binding("j", "scroll_down", "Down", show=False, priority=True),
        Binding("k", "scroll_up", "Up", show=False, priority=True),
        Binding("g", "scroll_home", "Top", show=False, priority=True),
        Binding("shift+g", "scroll_end", "Bottom", show=False, priority=True),
        Binding("/", "show_search", "Search", show=False, priority=True),
        Binding("q", "close_viewer", "Close", show=False, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._search_visible = False

    def compose(self) -> ComposeResult:
        yield Container(
            StatusBar(id="status-bar"),
            Horizontal(
                Static("Search", id="markdown-viewer-search-label"),
                Input(
                    placeholder="Search markdown",
                    id="markdown-viewer-search-input",
                ),
                id="markdown-viewer-search-row",
                classes="-hidden",
            ),
            MarkdownViewerWidget(id="markdown-viewer-body"),
            Static(id="markdown-viewer-footer", markup=False),
            ToastRack(id="toast-rack"),
            id="markdown-viewer-root",
        )

    def on_show(self) -> None:
        app = getattr(self, "app", None)
        store = getattr(app, "_store", None)
        if store is None:
            return
        self.update_from_state(store.snapshot())
        self.query_one(MarkdownViewerWidget).focus()

    def on_key(self, event: Any) -> None:
        key = getattr(event, "key", "")
        if key == "j":
            self.action_scroll_down()
            event.stop()
        elif key == "k":
            self.action_scroll_up()
            event.stop()
        elif key == "g":
            self.action_scroll_home()
            event.stop()
        elif key in {"G", "shift+g"}:
            self.action_scroll_end()
            event.stop()
        elif key == "/":
            self.action_show_search()
            event.stop()
        elif key == "q":
            self.action_close_viewer()
            event.stop()

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        self.query_one(MarkdownViewerWidget).update_markdown(selected_markdown_artifact(state))
        self._update_footer()

    def action_scroll_down(self) -> None:
        self.query_one(MarkdownViewerWidget).scroll_line(1)

    def action_scroll_up(self) -> None:
        self.query_one(MarkdownViewerWidget).scroll_line(-1)

    def action_scroll_home(self) -> None:
        self.query_one(MarkdownViewerWidget).scroll_to_home()

    def action_scroll_end(self) -> None:
        self.query_one(MarkdownViewerWidget).scroll_to_end()

    def action_show_search(self) -> None:
        search_row = self.query_one("#markdown-viewer-search-row", Horizontal)
        search_input = self.query_one("#markdown-viewer-search-input", Input)
        self._search_visible = True
        search_row.remove_class("-hidden")
        search_input.focus()
        self._update_footer()

    def action_close_viewer(self) -> None:
        self.app.action_back_dashboard()  # type: ignore[attr-defined]

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "markdown-viewer-search-input":
            return
        viewer = self.query_one(MarkdownViewerWidget)
        if (
            event.value.strip() == viewer.search_state.query
            and viewer.search_state.total_matches > 0
        ):
            viewer.find_next()
        else:
            viewer.begin_search(event.value)
        self._update_footer()

    def on_input_blurred(self, event: Input.Blurred) -> None:
        if event.input.id != "markdown-viewer-search-input":
            return
        self._hide_search()

    def _hide_search(self) -> None:
        search_row = self.query_one("#markdown-viewer-search-row", Horizontal)
        self._search_visible = False
        search_row.add_class("-hidden")
        self.query_one(MarkdownViewerWidget).focus()
        self._update_footer()

    def _update_footer(self) -> None:
        footer = "[J/K] Scroll   [g/G] Top/Bottom   [/] Search   [Q] Close"
        search_state = self.query_one(MarkdownViewerWidget).search_state
        if self._search_visible:
            footer = f"{footer}\nSearch: {self._search_status_text(search_state)}"
        elif search_state.query:
            footer = f"{footer}\nMatches: {self._search_status_text(search_state)}"
        self.query_one("#markdown-viewer-footer", Static).update(footer)

    @staticmethod
    def _search_status_text(search_state: MarkdownSearchState) -> str:
        if not search_state.query:
            return "enter query"
        if search_state.total_matches == 0:
            return f"no matches for '{search_state.query}'"
        return f"'{search_state.query}' {search_state.current_match}/{search_state.total_matches}"
