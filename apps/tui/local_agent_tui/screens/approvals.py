from __future__ import annotations

from ..compat import Binding, ComposeResult, Container, Screen, Static, _TEXTUAL_IMPORT_ERROR
from ..store.app_state import AppState
from ..store.selectors import footer_hints, pending_approvals, selected_approval_detail
from ..widgets.approval_detail import ApprovalDetailWidget
from ..widgets.approval_queue import ApprovalQueueWidget
from ..widgets.loading import loading_renderable
from ..widgets.status_bar import StatusBar
from ..widgets.toast import ToastRack


class ApprovalsScreen(Screen):  # type: ignore[misc]
    PANE_ORDER = ["approvals_queue", "approval_detail"]
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
        queue_focused = state.focused_pane == "approvals_queue"
        if state.approvals_request_status == "loading":
            self.query_one(ApprovalQueueWidget).show_loading(
                "Refreshing approvals...",
                focused=queue_focused,
                inbox_mode=True,
            )
            detail = self.query_one(ApprovalDetailWidget)
            detail.border_title = "Request Details"
            detail.set_class(state.focused_pane == "approval_detail", "-focused-pane")
            detail.update(loading_renderable("Loading approval details...", skeleton_lines=4))
            self.query_one("#approvals-screen-footer", Static).update(footer_hints(state, contextual=True))
            return
        self.query_one(ApprovalQueueWidget).update_approvals(
            pending_approvals(state),
            focused=queue_focused,
            inbox_mode=True,
        )
        detail_widget = self.query_one(ApprovalDetailWidget)
        detail_widget.set_class(state.focused_pane == "approval_detail", "-focused-pane")
        detail_widget.update_detail(selected_approval_detail(state))
        self.query_one("#approvals-screen-footer", Static).update(footer_hints(state, contextual=True))

    def action_approve_selected(self) -> None:
        self.app.action_approve_selected_request()  # type: ignore[attr-defined]

    def action_reject_selected(self) -> None:
        self.app.action_reject_selected_request()  # type: ignore[attr-defined]

    def action_show_scope(self) -> None:
        self.query_one(ApprovalDetailWidget).focus()
