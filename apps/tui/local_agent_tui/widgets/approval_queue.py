from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.text import Text

from ..store.selectors import ApprovalQueueItemViewModel
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
            self.update("No pending approvals.")
            return
        rendered_items: list[Text] = [
            Text("Task        Type             Policy              Status"),
            Text("----------- ---------------- ------------------- ----------"),
        ]
        for item in items:
            marker = ">" if item.is_selected else " "
            urgency = DANGER if item.status.lower() in {"pending", "waiting"} else WARNING
            row = Text()
            if item.is_highlighted:
                row.stylize("reverse")
            row.append(f"{marker} {item.task_id[:10]:<10} {item.request_type[:16]:<16} ")
            row.append(f"{item.policy_context[:19]:<19} ")
            row.append(f"{item.status.upper()[:10]:<10}", style=urgency)
            rendered_items.append(row)
            if inbox_mode:
                rendered_items.append(Text(f"  Action: {item.requested_action}"))
            rendered_items.append(Text(f"  {item.description}"))
        self.update(Group(*rendered_items))
