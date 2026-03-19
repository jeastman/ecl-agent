from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.markup import escape

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Container
    from textual.screen import ModalScreen
    from textual.widgets import Static, TextArea
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.binding import Binding
        from textual.containers import Container
        from textual.screen import ModalScreen
        from textual.widgets import Static, TextArea
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Binding = cast(Any, object)
        Container = cast(Any, object)
        ModalScreen = cast(Any, object)
        Static = cast(Any, object)
        TextArea = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class CreateTaskScreen(ModalScreen[None]):  # type: ignore[misc]
    BINDINGS = [Binding("ctrl+enter", "submit_task", "Submit", show=False, priority=True)]
    _DEFAULT_STATUS = "Enter adds a new line. Ctrl+Enter submits. Esc cancels."

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Create task", id="create-task-title"),
            Static("Describe the objective clearly. The runtime will create a fresh task from the current workspace.", id="create-task-subtitle"),
            TextArea("", placeholder="Describe the task objective", id="create-task-input"),
            Static(self._DEFAULT_STATUS, id="create-task-status"),
            Static("0 chars", id="create-task-count"),
            id="create-task-panel",
        )

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()

    def action_submit_task(self) -> None:
        input_widget = self.query_one("#create-task-input", TextArea)
        self.app.submit_create_task(input_widget.text)  # type: ignore[attr-defined]

    def set_status(self, message: str) -> None:
        self.query_one("#create-task-status", Static).update(escape(message))

    def reset_form(self) -> None:
        input_widget = self.query_one("#create-task-input", TextArea)
        input_widget.load_text("")
        input_widget.focus()
        self.set_status(self._DEFAULT_STATUS)
        self.query_one("#create-task-count", Static).update("0 chars")

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id != "create-task-input":
            return
        self.query_one("#create-task-count", Static).update(f"{len(event.text_area.text)} chars")

    def on_key(self, event: Any) -> None:
        key = getattr(event, "key", "")
        if key == "escape":
            self.app.close_create_task()  # type: ignore[attr-defined]
            event.stop()
