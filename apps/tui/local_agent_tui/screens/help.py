from __future__ import annotations

from rich.console import Group
from rich.text import Text

from ..compat import ComposeResult, Container, ModalScreen, Static, _TEXTUAL_IMPORT_ERROR
from ..store.app_state import AppState
from ..store.selectors import footer_hints


class HelpScreen(ModalScreen[None]):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            Static("Help", id="help-screen-title"),
            Static(id="help-screen-body"),
            id="help-screen-panel",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one("#help-screen-body", Static).update(_help_renderable(state))


def _help_renderable(state: AppState) -> Group:
    sections: list[object] = []

    overview = Text()
    overview.append("Operate the console with keyboard-first navigation. ", style="bold")
    overview.append("Use numbered pane jumps for the current screen, Tab to cycle, and G to open the command palette.")
    sections.extend([Text("Overview", style="bold"), overview, Text("")])

    sections.extend([Text("Current Screen", style="bold"), footer_hints(state, contextual=True), Text("")])

    sections.extend(
        [
            Text("Screen Shortcuts", style="bold"),
            Text("Dashboard", style="bold #9aa8b8"),
            footer_hints(_screen_state("dashboard"), contextual=True),
            Text(""),
            Text("Task Detail", style="bold #9aa8b8"),
            footer_hints(_screen_state("task_detail"), contextual=True),
            Text(""),
            Text("Approvals", style="bold #9aa8b8"),
            footer_hints(_screen_state("approvals"), contextual=True),
            Text(""),
            Text("Artifacts", style="bold #9aa8b8"),
            footer_hints(_screen_state("artifacts"), contextual=True),
            Text(""),
            Text("Memory", style="bold #9aa8b8"),
            footer_hints(_screen_state("memory"), contextual=True),
            Text(""),
            Text("Config", style="bold #9aa8b8"),
            footer_hints(_screen_state("config"), contextual=True),
            Text(""),
            Text("Diagnostics", style="bold #9aa8b8"),
            footer_hints(_screen_state("diagnostics"), contextual=True),
            Text(""),
        ]
    )

    palette = Text()
    palette.append("G", style="bold")
    palette.append(" opens the palette. ")
    palette.append("/task-id", style="bold")
    palette.append(" jumps directly to a task. Recent commands are shown when the query is empty.")
    sections.extend([Text("Command Palette", style="bold"), palette, Text("")])

    commands = Text()
    commands.append("Task commands: ", style="bold")
    commands.append("resume, authorize, reauthorize, complete-auth, revoke-auth, approvals, artifacts, diagnostics, memory, config")
    commands.append("\n")
    commands.append("Extended forms: ", style="bold")
    commands.append("cancel [reason], reply <message>")
    sections.extend([Text("Task Input", style="bold"), commands, Text("")])

    close = Text()
    close.append("Press ", style="none")
    close.append("Esc", style="bold")
    close.append(" or ")
    close.append("?", style="bold")
    close.append(" to close help.")
    sections.extend([Text("Close", style="bold"), close])

    return Group(*sections)


def _screen_state(screen_name: str) -> AppState:
    state = AppState(active_screen=screen_name)
    if screen_name == "task_detail":
        state.focused_pane = "timeline"
    return state
