from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.markup import escape

from ..store.app_state import AppState
from ..store.selectors import footer_hints, pending_approvals, selected_approval_detail
from ..widgets.approval_detail import ApprovalDetailWidget
from ..widgets.approval_queue import ApprovalQueueWidget
from ..widgets.status_bar import StatusBar
from ..theme.colors import TEXT_SECONDARY

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
            StatusBar(id="status-bar"),
            Container(
                ApprovalQueueWidget(id="approvals-screen-queue"),
                ApprovalDetailWidget(id="approvals-screen-detail"),
                id="approvals-screen-main",
            ),
            Static(id="approvals-screen-footer"),
            id="approvals-screen-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        self.query_one(ApprovalQueueWidget).update_approvals(
            pending_approvals(state),
            focused=True,
            inbox_mode=True,
        )
        self.query_one(ApprovalDetailWidget).update_detail(selected_approval_detail(state))
        footer = footer_hints(state)
        if state.approval_feedback:
            footer.append(f"\n{escape(state.approval_feedback)}", style=TEXT_SECONDARY)
        self.query_one("#approvals-screen-footer", Static).update(footer)
