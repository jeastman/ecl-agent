from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import footer_hints, pending_approvals
from ..widgets.approval_queue import ApprovalQueueWidget

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.screen import Screen
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container
        from textual.screen import Screen
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        Screen = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class ApprovalsScreen(Screen):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            ApprovalQueueWidget(id="approvals-screen-queue"),
            Static(id="approvals-screen-footer"),
            id="approvals-screen-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(ApprovalQueueWidget).update_approvals(
            pending_approvals(state),
            focused=True,
        )
        self.query_one("#approvals-screen-footer", Static).update("   ".join(footer_hints(state)))
