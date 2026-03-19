from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.text import Text

from ..renderables import badge, key_hints, text
from ..store.selectors import TaskActionBarViewModel
from ..theme.colors import DANGER, SUCCESS, TEXT_MUTED_DEEP, TEXT_SECONDARY, WARNING
from ..theme.typography import key_hint

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.widgets import Input, Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container
        from textual.widgets import Input, Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        Input = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class InputBoxWidget(Container):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Static(id="task-detail-command-status")
        yield Input(
            placeholder="Enter a task command",
            id="task-detail-command-input",
            disabled=True,
        )

    def update_actions(self, model: TaskActionBarViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Actions"
        input_widget = self.query_one("#task-detail-command-input", Input)
        input_widget.placeholder = model.input_placeholder
        hints: list[Text] = []
        if model.resume_enabled:
            hints.append(key_hint("R", "Resume"))
        if model.approvals_enabled:
            hints.append(key_hint("A", f"Approvals {model.approval_count}"))
        if model.artifact_open_enabled:
            hints.append(key_hint("O", "Artifacts"))
        if model.artifact_external_open_enabled:
            hints.append(key_hint("E", "External Open"))
        if model.diagnostics_enabled:
            hints.append(key_hint("D", "Diagnostics"))
        if model.logs_toggle_enabled:
            hints.append(key_hint("L", "Hide Logs" if model.logs_visible else "Logs"))
        if model.back_enabled:
            hints.append(key_hint("Esc", "Back"))
        status = Text(model.status_message, style=_status_tone_style(model.status_tone))
        if hints:
            hint_row = Text()
            for index, hint in enumerate(hints):
                if index:
                    hint_row.append("   ", style=TEXT_SECONDARY)
                hint_row.append_text(hint)
            status.append("\n")
            status.append_text(hint_row)
        self.query_one("#task-detail-command-status", Static).update(status)

    def focus_input(self) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        input_widget = self.query_one("#task-detail-command-input", Input)
        input_widget.disabled = False
        input_widget.focus()

    def clear_input(self) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        input_widget = self.query_one("#task-detail-command-input", Input)
        input_widget.value = ""
        input_widget.disabled = True

    def blur_input(self) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        input_widget = self.query_one("#task-detail-command-input", Input)
        input_widget.disabled = True

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "task-detail-command-input":
            return
        self.app.handle_task_detail_command(event.value)  # type: ignore[attr-defined]


def _status_tone_style(tone: str) -> str:
    return {
        "danger": DANGER,
        "success": SUCCESS,
        "warning": WARNING,
    }.get(tone, TEXT_MUTED_DEEP)
