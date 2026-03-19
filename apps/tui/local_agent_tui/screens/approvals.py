from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import footer_hints, pending_approvals, selected_approval_detail
from ..widgets.approval_detail import ApprovalDetailWidget
from ..widgets.approval_queue import ApprovalQueueWidget
from ..widgets.loading import loading_renderable
from ..widgets.status_bar import StatusBar
from ..widgets.toast import ToastRack

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Container
    from textual.screen import Screen
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.binding import Binding
        from textual.containers import Container
        from textual.screen import Screen
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Binding = cast(Any, object)
        Container = cast(Any, object)
        Screen = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class ApprovalsScreen(Screen):  # type: ignore[misc]
    BINDINGS = [
        Binding("y", "approve_selected", "Approve", show=False, priority=True),
        Binding("n", "reject_selected", "Reject", show=False, priority=True),
        Binding("enter", "show_scope", "Details", show=False, priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            StatusBar(id="status-bar"),
            Container(
                ApprovalQueueWidget(id="approvals-screen-queue"),
                ApprovalDetailWidget(id="approvals-screen-detail"),
                id="approvals-screen-main",
            ),
            Static(id="approvals-screen-footer"),
            ToastRack(id="toast-rack"),
            id="approvals-screen-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        if state.approvals_request_status == "loading":
            self.query_one(ApprovalQueueWidget).show_loading(
                "Refreshing approvals...",
                focused=True,
                inbox_mode=True,
            )
            detail = self.query_one(ApprovalDetailWidget)
            detail.border_title = "Request Details"
            detail.update(loading_renderable("Loading approval details...", skeleton_lines=4))
            self.query_one("#approvals-screen-footer", Static).update(footer_hints(state))
            return
        self.query_one(ApprovalQueueWidget).update_approvals(
            pending_approvals(state),
            focused=True,
            inbox_mode=True,
        )
        self.query_one(ApprovalDetailWidget).update_detail(selected_approval_detail(state))
        self.query_one("#approvals-screen-footer", Static).update(footer_hints(state))

    def action_approve_selected(self) -> None:
        self.app.action_approve_selected_request()  # type: ignore[attr-defined]

    def action_reject_selected(self) -> None:
        self.app.action_reject_selected_request()  # type: ignore[attr-defined]

    def action_show_scope(self) -> None:
        self.query_one(ApprovalDetailWidget).focus()
