from __future__ import annotations

from typing import Any

from rich.markup import escape

from ..compat import ComposeResult, Container, Input, ModalScreen, Static, _TEXTUAL_IMPORT_ERROR


class RuntimeUserPromptScreen(ModalScreen[None]):  # type: ignore[misc]
    _DEFAULT_STATUS = "Enter the runtime user ID used for per-user remote MCP authorization."

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Runtime User", id="runtime-user-title"),
            Static(
                "This ID is attached to new tasks and remote MCP authorization requests.",
                id="runtime-user-subtitle",
            ),
            Input(placeholder="runtime user id", id="runtime-user-input"),
            Static(self._DEFAULT_STATUS, id="runtime-user-status"),
            id="runtime-user-panel",
        )

    def set_value(self, value: str | None) -> None:
        self.query_one("#runtime-user-input", Input).value = value or ""

    def set_status(self, message: str) -> None:
        self.query_one("#runtime-user-status", Static).update(escape(message))

    def focus_input(self) -> None:
        self.query_one("#runtime-user-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.app.submit_runtime_user_id(event.value)  # type: ignore[attr-defined]

    def on_key(self, event: Any) -> None:
        if getattr(event, "key", "") == "escape":
            self.app.close_runtime_user_prompt()  # type: ignore[attr-defined]
            event.stop()
