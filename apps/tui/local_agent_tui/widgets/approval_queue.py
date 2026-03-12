from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.selectors import ApprovalQueueItemViewModel

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
        self.set_class(focused, "-focused-pane")
        if not items:
            self.update("No pending approvals.")
            return
        rendered_items: list[str] = []
        for item in items:
            marker = ">" if item.is_selected else " "
            if inbox_mode:
                rendered_items.append(
                    "\n".join(
                        [
                            (
                                f"{marker} {item.task_id}  {item.request_type}  "
                                f"{item.policy_context}  {item.status.upper()}"
                            ),
                            f"  Action: {item.requested_action}",
                            f"  {item.description}",
                        ]
                    )
                )
            else:
                rendered_items.append(
                    "\n".join(
                        [
                            f"{marker} {item.task_id}  {item.status.upper()}",
                            item.description,
                            item.scope_summary,
                        ]
                    )
                )
        self.update("\n".join(rendered_items))
