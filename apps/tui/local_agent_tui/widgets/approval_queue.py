from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.text import Text

from ..store.selectors import ApprovalQueueItemViewModel
from ..theme.empty_states import render_empty_state
from ..theme.colors import DANGER, WARNING
from ..theme.typography import muted, status_badge
from ..utils.text import truncate_id

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


class ApprovalQueueWidget(Static):  # type: ignore[misc]
    def update_approvals(
        self,
        items: list[ApprovalQueueItemViewModel],
        *,
        focused: bool,
        inbox_mode: bool = False,
    ) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Approval Requests" if inbox_mode else "Approvals Pending"
        self.border_subtitle = "Focused" if focused else ""
        self.set_class(focused, "-focused-pane")
        if not items:
            self.update(render_empty_state("approvals"))
            return
        self.update(Group(*[_approval_card(item, inbox_mode=inbox_mode) for item in items]))


def _approval_card(item: ApprovalQueueItemViewModel, *, inbox_mode: bool) -> Text:
    urgency = DANGER if item.status.lower() in {"pending", "waiting"} else WARNING
    text = Text()
    if item.is_selected or item.is_highlighted:
        text.append("▶ ", style=urgency)
    else:
        text.append("  ")
    text.append(item.request_type, style="bold")
    text.append(" ")
    text.append_text(status_badge(item.status))
    text.append("\n")
    text.append(truncate_id(item.task_id, width=18), style="bold")
    if item.run_id:
        text.append("  ")
        text.append(truncate_id(item.run_id, width=18), style=muted("").style)
    text.append("\n")
    text.append(item.description)
    text.append("\n")
    text.append(item.requested_action, style=muted("").style)
    text.append("   ", style=muted("").style)
    text.append(item.policy_context, style=muted("").style)
    text.append("\n")
    text.append(item.scope_summary, style=muted("").style)
    text.append("   ", style=muted("").style)
    text.append(item.created_at_relative, style=muted("").style)
    if inbox_mode:
        text.append("\n")
        text.append(f"Action: {item.requested_action}", style=muted("").style)
    return text
