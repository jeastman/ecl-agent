from __future__ import annotations

from typing import Any

from ..compat import Binding, Button, ComposeResult, Container, ModalScreen, Static, _TEXTUAL_IMPORT_ERROR


class ConfirmDialogScreen(ModalScreen[bool]):  # type: ignore[misc]
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False, priority=True),
        Binding("enter", "confirm", "Confirm", show=False, priority=True),
    ]

    def __init__(
        self,
        *,
        title: str,
        body: str,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        danger: bool = False,
    ) -> None:
        super().__init__()
        self._title = title
        self._body = body
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label
        self._danger = danger

    def compose(self) -> ComposeResult:
        confirm_classes = "confirm-dialog-button -danger" if self._danger else "confirm-dialog-button"
        yield Container(
            Static(self._title, id="confirm-dialog-title"),
            Static(self._body, id="confirm-dialog-body"),
            Container(
                Button(self._cancel_label, id="confirm-dialog-cancel", classes="confirm-dialog-button"),
                Button(self._confirm_label, id="confirm-dialog-confirm", classes=confirm_classes),
                id="confirm-dialog-actions",
            ),
            id="confirm-dialog-panel",
            classes="-danger" if self._danger else "",
        )

    def on_mount(self) -> None:
        self.query_one("#confirm-dialog-confirm", Button).focus()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def on_button_pressed(self, event: Any) -> None:
        if event.button.id == "confirm-dialog-confirm":
            self.dismiss(True)
            return
        if event.button.id == "confirm-dialog-cancel":
            self.dismiss(False)
