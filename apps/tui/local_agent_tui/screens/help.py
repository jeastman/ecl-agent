from __future__ import annotations

from rich.console import Group, RenderableType
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from ..compat import ComposeResult, Container, Key, ModalScreen, Static, VerticalScroll, _TEXTUAL_IMPORT_ERROR
from ..store.app_state import AppState
from ..store.selectors import _footer_hint_labels


class HelpScreen(ModalScreen[None]):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            Static("Help", id="help-screen-title"),
            Static(
                "Keyboard-first navigation, task actions, and screen-specific shortcuts.",
                id="help-screen-subtitle",
            ),
            VerticalScroll(
                Static(id="help-screen-body"),
                id="help-screen-scroll",
            ),
            Static("Use ↑/↓, Page Up/Down, Home/End, Esc, or ?.", id="help-screen-footer"),
            id="help-screen-panel",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one("#help-screen-body", Static).update(_help_renderable(state))

    def on_mount(self) -> None:
        self.query_one("#help-screen-scroll", VerticalScroll).focus()

    def on_key(self, event: Key) -> None:
        scroll = self.query_one("#help-screen-scroll", VerticalScroll)
        key = event.key
        if key in {"up", "k"}:
            scroll.action_scroll_up()
            event.stop()
        elif key in {"down", "j"}:
            scroll.action_scroll_down()
            event.stop()
        elif key == "pageup":
            scroll.action_page_up()
            event.stop()
        elif key == "pagedown":
            scroll.action_page_down()
            event.stop()
        elif key == "home":
            scroll.scroll_home(animate=False)
            event.stop()
        elif key == "end":
            scroll.scroll_end(animate=False)
            event.stop()


def _help_renderable(state: AppState) -> Group:
    sections: list[RenderableType] = []

    overview = Text()
    overview.append("Operate the console with keyboard-first navigation. ", style="bold")
    overview.append(
        "Use the command palette for discovery, Tab to cycle panes, and direct keys for the highest-signal actions."
    )
    sections.extend(
        [
            _section_title("Overview"),
            overview,
            Text(""),
            _section_title("Current Screen"),
            _shortcut_table(_screen_shortcuts(state)),
            Text(""),
            _section_title("Screen Shortcuts"),
        ]
    )

    for screen_name in ("dashboard", "task_detail", "approvals", "artifacts", "memory", "config", "diagnostics"):
        sections.append(_subsection_title(_screen_label(screen_name)))
        sections.append(_shortcut_table(_screen_shortcuts(_screen_state(screen_name))))
        sections.append(Text(""))

    palette = Text()
    palette.append("G", style="bold")
    palette.append(" opens the command palette. ")
    palette.append("/task-id", style="bold")
    palette.append(" jumps directly to a task. Recent commands appear when the query is empty.")
    sections.extend([_section_title("Command Palette"), palette, Text("")])

    commands = Text()
    commands.append("Task commands: ", style="bold")
    commands.append(
        "resume, authorize, reauthorize, complete-auth, revoke-auth, approvals, artifacts, diagnostics, memory, config"
    )
    commands.append("\n")
    commands.append("Extended forms: ", style="bold")
    commands.append("cancel [reason], reply <message>")
    sections.extend([_section_title("Task Input"), commands, Text("")])

    close = Text()
    close.append("Press ", style="none")
    close.append("Esc", style="bold")
    close.append(" or ")
    close.append("?", style="bold")
    close.append(" to close help.")
    sections.extend([_section_title("Close"), close])

    return Group(*sections)


def _section_title(title: str) -> Rule:
    return Rule(title, style="#67b7dc")


def _subsection_title(title: str) -> Text:
    return Text(title, style="bold #9aa8b8")


def _shortcut_table(hints: list[tuple[str, str]]) -> Table:
    table = Table.grid(expand=True, padding=(0, 2))
    table.add_column(width=16, style="bold #f1f6f8", no_wrap=True)
    table.add_column(ratio=1, style="#b2bcc4")
    for key, action in hints:
        table.add_row(key, action)
    return table


def _screen_shortcuts(state: AppState) -> list[tuple[str, str]]:
    labels = _footer_hint_labels(state, contextual=True, compact=False)
    shortcuts: list[tuple[str, str]] = []
    for label in labels:
        key, _, action = label.partition(" ")
        shortcuts.append((key, action))
    return shortcuts


def _screen_label(screen_name: str) -> str:
    return {
        "dashboard": "Dashboard",
        "task_detail": "Task Detail",
        "approvals": "Approvals",
        "artifacts": "Artifacts",
        "memory": "Memory",
        "config": "Config",
        "diagnostics": "Diagnostics",
    }[screen_name]


def _screen_state(screen_name: str) -> AppState:
    state = AppState(active_screen=screen_name)
    if screen_name == "task_detail":
        state.focused_pane = "timeline"
    return state
