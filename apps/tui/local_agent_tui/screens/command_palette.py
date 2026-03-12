from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import CommandPaletteItemViewModel, command_palette

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.screen import ModalScreen
    from textual.widgets import Input, Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container
        from textual.screen import ModalScreen
        from textual.widgets import Input, Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        ModalScreen = cast(Any, object)
        Input = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class CommandPaletteScreen(ModalScreen[None]):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            Input(placeholder="Type a command", id="command-palette-input"),
            Static(id="command-palette-results"),
            id="command-palette-panel",
        )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        model = command_palette(state)
        input_widget = self.query_one(Input)
        if input_widget.value != model.query:
            input_widget.value = model.query
        self.query_one("#command-palette-results", Static).update(_render_results(model.items))

    def on_input_changed(self, event: Input.Changed) -> None:
        self.app.handle_command_palette_query_changed(event.value)  # type: ignore[attr-defined]

    def on_input_submitted(self, event: Input.Submitted) -> None:
        del event
        self.app.action_run_palette_command()  # type: ignore[attr-defined]

    def on_key(self, event: Any) -> None:
        key = getattr(event, "key", "")
        if key in {"up", "k"}:
            self.app.move_command_palette_selection(-1)  # type: ignore[attr-defined]
            event.stop()
        elif key in {"down", "j"}:
            self.app.move_command_palette_selection(1)  # type: ignore[attr-defined]
            event.stop()
        elif key == "escape":
            self.app.close_command_palette()  # type: ignore[attr-defined]
            event.stop()


def _render_results(items: list[CommandPaletteItemViewModel]) -> str:
    if not items:
        return "No matching commands."
    lines: list[str] = []
    for item in items:
        marker = ">" if item.is_selected else " "
        lines.append(f"{marker} {_highlight_matches(item.label, item.match_spans)}")
        lines.append(f"  {item.hint}")
    return "\n".join(lines)


def _highlight_matches(text: str, spans: list[tuple[int, int]]) -> str:
    if not spans:
        return text
    rendered: list[str] = []
    cursor = 0
    for start, end in spans:
        if start > cursor:
            rendered.append(text[cursor:start])
        rendered.append(f"[reverse]{text[start:end]}[/reverse]")
        cursor = end
    if cursor < len(text):
        rendered.append(text[cursor:])
    return "".join(rendered)
