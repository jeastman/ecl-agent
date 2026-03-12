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
    def update_approvals(self, items: list[ApprovalQueueItemViewModel], *, focused: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Approvals Pending"
        self.set_class(focused, "-focused-pane")
        if not items:
            self.update("No pending approvals.")
            return
        self.update(
            "\n".join(
                "\n".join(
                    [
                        f"{'>' if item.is_selected else ' '} {item.task_id}  {item.status.upper()}",
                        item.description,
                        item.scope_summary,
                    ]
                )
                for item in items
            )
        )
