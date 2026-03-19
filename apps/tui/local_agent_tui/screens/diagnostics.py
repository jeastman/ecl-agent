from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from ..store.app_state import AppState
from ..store.selectors import DiagnosticsItemViewModel, diagnostics_items, footer_hints, selected_diagnostics_detail
from ..widgets.loading import loading_renderable
from ..widgets.status_bar import StatusBar
from ..widgets.toast import ToastRack

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.screen import Screen
    from textual.widgets import Label, ListItem, ListView, Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container
        from textual.screen import Screen
        from textual.widgets import Label, ListItem, ListView, Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        Screen = cast(Any, object)
        Label = cast(Any, object)
        ListItem = cast(Any, object)
        ListView = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class DiagnosticRow(ListItem):  # type: ignore[misc]
    def __init__(self, item: DiagnosticsItemViewModel) -> None:
        self.diagnostic_id = item.diagnostic_id
        self.item = item
        super().__init__(Label(_render_diagnostic_list_item(item)))


class DiagnosticsListWidget(ListView):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._signature: tuple[tuple[str, bool], ...] = ()

    def update_items(self, items: list[DiagnosticsItemViewModel], *, focused: bool) -> None:
        signature = tuple((item.diagnostic_id, item.is_selected) for item in items)
        self.border_title = "Diagnostics"
        self.border_subtitle = "Focused" if focused else ""
        self.set_class(focused, "-focused-pane")
        if signature != self._signature:
            self.clear()
            selected_index = None
            for index, item in enumerate(items):
                self.append(DiagnosticRow(item))
                if item.is_selected:
                    selected_index = index
            if selected_index is not None:
                self.index = selected_index
            self._signature = signature

    def show_loading(self, label: str, *, focused: bool) -> None:
        self.border_title = "Diagnostics"
        self.border_subtitle = "Focused" if focused else ""
        self.set_class(focused, "-focused-pane")
        self.clear()
        self.append(ListItem(Label(Text(label))))
        self._signature = ()


class DiagnosticsScreen(Screen):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            StatusBar(id="status-bar"),
            Container(
                DiagnosticsListWidget(id="diagnostics-screen-list"),
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
        list_panel = self.query_one(DiagnosticsListWidget)
        if state.diagnostics_request_status == "loading":
            list_panel.show_loading("Loading diagnostics...", focused=True)
            detail_panel = self.query_one("#diagnostics-screen-detail", Static)
            detail_panel.border_title = "Diagnostics"
            detail_panel.update(loading_renderable("Loading diagnostic details...", skeleton_lines=5))
            self.query_one("#diagnostics-screen-footer", Static).update(footer_hints(state))
            return
        items = diagnostics_items(state)
        list_panel.update_items(items, focused=True)
        if not items:
            list_panel.clear()
            list_panel.append(ListItem(Label(Text("No diagnostics."))))
        detail = selected_diagnostics_detail(state)
        detail_panel = self.query_one("#diagnostics-screen-detail", Static)
        detail_panel.border_title = detail.title
        detail_panel.update(
            _render_diagnostic_detail(
                detail.title,
                detail.summary,
                detail.message,
                detail.stack_trace,
                detail.resolution,
            )
        )
        self.query_one("#diagnostics-screen-footer", Static).update(footer_hints(state))

    def on_list_view_highlighted(self, message: ListView.Highlighted) -> None:
        if message.list_view.id != "diagnostics-screen-list":
            return
        item = message.item
        if isinstance(item, DiagnosticRow):
            self.app._store.dispatch({"kind": "ui", "selected_diagnostic_id": item.diagnostic_id})  # type: ignore[attr-defined]
            self.app._render_state()  # type: ignore[attr-defined]


def _render_diagnostic_list_item(item: Any) -> Text:
    rendered = Text()
    icon = getattr(item, "icon", "!")
    severity_label = getattr(item, "severity_label", "INFO")
    created = getattr(item, "created_at_relative", getattr(item, "created_at", ""))
    tone = getattr(item, "tone", "info")
    tone_style = {
        "danger": "bold #d96c6c",
        "warning": "bold #f0c36a",
        "success": "bold #5cb85c",
    }.get(tone, "bold #67b7dc")
    rendered.append("▎ ", style=tone_style)
    rendered.append(f"{icon} ", style=tone_style)
    rendered.append(f"{severity_label}  ", style=tone_style)
    rendered.append(item.kind, style="bold")
    rendered.append(f"  {created}")
    rendered.append("\n")
    rendered.append(item.message)
    return rendered


def _render_diagnostic_detail(
    title: str,
    summary: str,
    message: str,
    stack_trace: str = "",
    resolution: str = "",
) -> Group:
    renderables: list[Any] = [Text(summary), Text(""), Text("Message", style="bold"), Text(message)]
    if stack_trace:
        renderables.extend([Text(""), Text("Stack Trace", style="bold"), Syntax(stack_trace, "text", word_wrap=True, line_numbers=False)])
    if resolution:
        renderables.extend([Text(""), Text("Suggested Resolution", style="bold"), Text(resolution)])
    return Group(*renderables)
