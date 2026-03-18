from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.markup import escape

from ..store.selectors import ApprovalDetailViewModel
from ..theme.colors import DANGER, WARNING

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class ApprovalDetailWidget(Static):  # type: ignore[misc]
    def update_detail(self, detail: ApprovalDetailViewModel | None) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Request Details"
        if detail is None:
            self.update("Select an approval to inspect its details.")
            return
        lines = [
            f"Task: {escape(detail.task_id)}",
            f"Run: {escape(detail.run_id)}",
            f"Approval: {escape(detail.approval_id)}",
            f"Type: {escape(detail.request_type)}",
            f"Policy: {escape(detail.policy_context)}",
            f"Action: {escape(detail.requested_action)}",
            f"Status: [{DANGER if detail.status in {'pending', 'waiting'} else WARNING}]{escape(detail.status)}[/]",
            f"Created: {escape(detail.created_at)}",
            "",
            "Description",
            escape(detail.description),
            "",
            "Scope",
            escape(detail.scope_summary),
        ]
        self.update("\n".join(lines))
