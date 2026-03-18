from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.text import Text

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
        status = Text("Status: ")
        status.append(
            detail.status,
            style=DANGER if detail.status in {"pending", "waiting"} else WARNING,
        )
        self.update(
            Group(
                Text(f"Task: {detail.task_id}"),
                Text(f"Run: {detail.run_id}"),
                Text(f"Approval: {detail.approval_id}"),
                Text(f"Type: {detail.request_type}"),
                Text(f"Policy: {detail.policy_context}"),
                Text(f"Action: {detail.requested_action}"),
                status,
                Text(f"Created: {detail.created_at}"),
                Text(""),
                Text("Description"),
                Text(detail.description),
                Text(""),
                Text("Scope"),
                Text(detail.scope_summary),
            )
        )
