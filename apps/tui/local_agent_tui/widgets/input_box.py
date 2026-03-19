from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.text import Text

from ..renderables import badge, key_hints, text
from ..store.selectors import TaskActionBarViewModel

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
        yield Input(
            placeholder="Enter a task command",
            id="task-detail-command-input",
            disabled=True,
        )
        yield Static(id="task-detail-command-status", markup=False)

    def update_actions(self, model: TaskActionBarViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Command / Actions"
        input_widget = self.query_one("#task-detail-command-input", Input)
        input_widget.placeholder = model.input_placeholder
        hints: list[str] = []
        if model.resume_enabled:
            hints.append("[R] Resume")
        if model.approvals_enabled:
            hints.append("[A] Approvals")
        if model.artifact_open_enabled:
            hints.append("[O] Artifact")
        if model.artifact_external_open_enabled:
            hints.append("[E] External Open")
        if model.diagnostics_enabled:
            hints.append("[D] Diagnostics")
        if model.logs_toggle_enabled:
            hints.append("[L] Hide Logs" if model.logs_visible else "[L] Show Logs")
        if model.back_enabled:
            hints.append("[Esc] Back")
        renderables: list[Text] = [text(model.status_message)]
        if hints:
            renderables.extend([Text(""), key_hints(hints)])
        self.query_one("#task-detail-command-status", Static).update(Group(*renderables))

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
