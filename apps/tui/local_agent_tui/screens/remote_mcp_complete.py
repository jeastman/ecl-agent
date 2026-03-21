from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.markup import escape

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


class RemoteMCPCompleteScreen(ModalScreen[None]):  # type: ignore[misc]
    _DEFAULT_STATUS = "Paste the returned authorization code and state token. Ctrl+Enter submits."

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Complete Remote MCP Authorization", id="remote-mcp-complete-title"),
            Static(id="remote-mcp-complete-subtitle"),
            Input(placeholder="authorization code", id="remote-mcp-complete-code"),
            Input(placeholder="state token", id="remote-mcp-complete-state"),
            Static(self._DEFAULT_STATUS, id="remote-mcp-complete-status"),
            id="remote-mcp-complete-panel",
        )

    def update_context(self, *, server_name: str, provider_id: str) -> None:
        self.query_one("#remote-mcp-complete-subtitle", Static).update(
            escape(
                f"Submit the returned credentials for remote MCP server {server_name} ({provider_id})."
            )
        )

    def set_state_token(self, token: str | None) -> None:
        self.query_one("#remote-mcp-complete-state", Input).value = token or ""

    def set_status(self, message: str) -> None:
        self.query_one("#remote-mcp-complete-status", Static).update(escape(message))

    def focus_input(self) -> None:
        self.query_one("#remote-mcp-complete-code", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "remote-mcp-complete-code":
            self.query_one("#remote-mcp-complete-state", Input).focus()
            return
        self.app.submit_remote_mcp_complete()  # type: ignore[attr-defined]

    def on_key(self, event: Any) -> None:
        key = getattr(event, "key", "")
        if key == "escape":
            self.app.close_remote_mcp_complete()  # type: ignore[attr-defined]
            event.stop()
        elif key == "ctrl+enter":
            self.app.submit_remote_mcp_complete()  # type: ignore[attr-defined]
            event.stop()
