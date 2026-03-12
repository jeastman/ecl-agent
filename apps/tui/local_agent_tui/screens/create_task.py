from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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


class CreateTaskScreen(ModalScreen[None]):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            Static("Create task", id="create-task-title"),
            Input(placeholder="Objective", id="create-task-input"),
            Static("Enter submits. Esc cancels.", id="create-task-status"),
            id="create-task-panel",
        )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.app.submit_create_task(event.value)  # type: ignore[attr-defined]

    def set_status(self, message: str) -> None:
        self.query_one("#create-task-status", Static).update(message)

    def on_key(self, event: Any) -> None:
        if getattr(event, "key", "") == "escape":
            self.app.close_create_task()  # type: ignore[attr-defined]
            event.stop()
