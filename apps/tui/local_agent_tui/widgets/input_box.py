from __future__ import annotations

from rich.text import Text

from ..compat import ComposeResult, Container, Input, Key, Static, _TEXTUAL_IMPORT_ERROR
from ..store.selectors import TaskActionBarViewModel
from ..theme.colors import DANGER, SUCCESS, TEXT_MUTED_DEEP, TEXT_SECONDARY, WARNING
from ._dirty import DirtyCheckMixin


class InputBoxWidget(DirtyCheckMixin, Container):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Static(id="task-detail-command-status")
        yield Static(id="task-detail-command-suggestion")
        yield Input(
            placeholder="Enter a task command",
            id="task-detail-command-input",
            disabled=True,
        )

    def update_actions(self, model: TaskActionBarViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Actions"
        if not self._should_render(model):
            return
        input_widget = self.query_one("#task-detail-command-input", Input)
        input_widget.placeholder = model.input_placeholder
        suggestion_widget = self.query_one("#task-detail-command-suggestion", Static)
        status = Text(model.status_message, style=_status_tone_style(model.status_tone))
        self.query_one("#task-detail-command-status", Static).update(status)
        suggestion = Text()
        if model.input_suggestion:
            suggestion.append("Tab ", style=TEXT_SECONDARY)
            suggestion.append(model.input_suggestion, style=TEXT_MUTED_DEEP)
        if model.input_history_hint:
            if suggestion:
                suggestion.append("   ", style=TEXT_SECONDARY)
            suggestion.append(model.input_history_hint, style=TEXT_MUTED_DEEP)
        suggestion_widget.update(suggestion)

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

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "task-detail-command-input":
            return
        self.app.handle_task_command_text_changed(event.value)  # type: ignore[attr-defined]

    def on_key(self, event: Key) -> None:
        input_widget = self.query_one("#task-detail-command-input", Input)
        if event.key == "up" and input_widget.has_focus:
            self.app.cycle_task_command_history(-1)  # type: ignore[attr-defined]
            event.stop()
            return
        if event.key == "down" and input_widget.has_focus:
            self.app.cycle_task_command_history(1)  # type: ignore[attr-defined]
            event.stop()
            return
        if event.key == "tab" and input_widget.has_focus:
            self.app.complete_task_command_input()  # type: ignore[attr-defined]
            event.stop()
            return
        if event.key == "enter" and input_widget.has_focus:
            self.app.handle_task_detail_command(input_widget.value)  # type: ignore[attr-defined]
            event.stop()
            return

    def set_input_value(self, value: str) -> None:
        input_widget = self.query_one("#task-detail-command-input", Input)
        input_widget.value = value


def _status_tone_style(tone: str) -> str:
    return {
        "danger": DANGER,
        "success": SUCCESS,
        "warning": WARNING,
    }.get(tone, TEXT_MUTED_DEEP)
