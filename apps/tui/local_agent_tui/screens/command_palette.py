from __future__ import annotations

from typing import Any

from rich.console import Group
from rich.table import Table
from rich.text import Text

from ..compat import ComposeResult, Container, Input, ModalScreen, Static, _TEXTUAL_IMPORT_ERROR
from ..store.app_state import AppState
from ..store.selectors import CommandPaletteItemViewModel, command_palette


class CommandPaletteScreen(ModalScreen[None]):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            Static("Command Palette", id="command-palette-title"),
            Input(placeholder="Search commands", id="command-palette-input"),
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
        self.query_one("#command-palette-results", Static).update(_render_results(model))

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


def _render_results(model: Any) -> Group:
    if not model.items:
        return Group(Text(model.empty_message or "No matching commands."), Text("0 results", style="dim"))
    lines: list[Any] = []
    last_category: str | None = None
    for item in model.items:
        if item.category != last_category:
            lines.append(Text(f"─ {item.category} ─", style="bold"))
            last_category = item.category
        lines.append(_render_item(item))
    lines.append(Text(f"{model.result_count} result{'s' if model.result_count != 1 else ''}", style="dim"))
    return Group(*lines)


def _render_item(item: CommandPaletteItemViewModel) -> Table:
    table = Table.grid(expand=True)
    table.add_column(ratio=1)
    table.add_column(width=12, justify="right")
    label = Text()
    label.append("▎ " if item.is_selected else "  ")
    label.append(f"{item.icon} ")
    label.append_text(_highlight_matches(item.label, item.match_spans))
    label.append("  ")
    label.append(item.description, style="dim")
    hint = Text()
    hint.append("   ")
    hint.append(item.hint, style="dim")
    left = Group(label, hint)
    shortcut = Text(item.shortcut or "", style="bold #9aa8b8")
    table.add_row(left, shortcut)
    return table


def _highlight_matches(text_value: str, spans: list[tuple[int, int]]) -> Text:
    if not spans:
        return Text(text_value)
    rendered = Text()
    cursor = 0
    for start, end in spans:
        if start > cursor:
            rendered.append(text_value[cursor:start])
        rendered.append(text_value[start:end], style="bold #67b7dc")
        cursor = end
    if cursor < len(text_value):
        rendered.append(text_value[cursor:])
    return rendered
