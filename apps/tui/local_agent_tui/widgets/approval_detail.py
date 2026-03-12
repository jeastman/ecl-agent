from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
            f"Task: {detail.task_id}",
            f"Run: {detail.run_id}",
            f"Approval: {detail.approval_id}",
            f"Type: {detail.request_type}",
            f"Policy: {detail.policy_context}",
            f"Action: {detail.requested_action}",
            f"Status: [{DANGER if detail.status in {'pending', 'waiting'} else WARNING}]{detail.status}[/]",
            f"Created: {detail.created_at}",
            "",
            "Description",
            detail.description,
            "",
            "Scope",
            detail.scope_summary,
        ]
        self.update("\n".join(lines))
