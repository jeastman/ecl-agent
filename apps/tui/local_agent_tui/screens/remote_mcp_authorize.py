from __future__ import annotations

from typing import Any

from rich.markup import escape

from ..compat import ComposeResult, Container, ModalScreen, Static, _TEXTUAL_IMPORT_ERROR


class RemoteMCPAuthorizeScreen(ModalScreen[None]):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            Static("Remote MCP Authorization", id="remote-mcp-authorize-title"),
            Static(id="remote-mcp-authorize-subtitle"),
            Static(id="remote-mcp-authorize-url"),
            Static(
                "Keys: O open browser, Y copy URL, Enter continue to code/state entry, Esc close.",
                id="remote-mcp-authorize-status",
            ),
            id="remote-mcp-authorize-panel",
        )

    def update_content(self, *, server_name: str, provider_id: str, authorization_url: str) -> None:
        self.query_one("#remote-mcp-authorize-subtitle", Static).update(
            escape(
                f"Authorize remote MCP server {server_name} with provider {provider_id}, then return here."
            )
        )
        self.query_one("#remote-mcp-authorize-url", Static).update(escape(authorization_url))

    def set_status(self, message: str) -> None:
        self.query_one("#remote-mcp-authorize-status", Static).update(escape(message))

    def on_key(self, event: Any) -> None:
        key = getattr(event, "key", "")
        if key == "escape":
            self.app.close_remote_mcp_authorize()  # type: ignore[attr-defined]
            event.stop()
        elif key == "enter":
            self.app.open_remote_mcp_complete()  # type: ignore[attr-defined]
            event.stop()
        elif key == "o":
            self.app.action_open_remote_mcp_authorization_url()  # type: ignore[attr-defined]
            event.stop()
        elif key == "y":
            self.app.action_copy_remote_mcp_authorization_url()  # type: ignore[attr-defined]
            event.stop()
