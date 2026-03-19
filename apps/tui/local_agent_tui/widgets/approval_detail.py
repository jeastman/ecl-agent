from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.table import Table
from rich.text import Text

from ..store.selectors import ApprovalDetailViewModel
from ..theme.colors import DANGER, TEXT_MUTED_DEEP, WARNING
from ..theme.typography import key_hint, status_badge, title

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
        metadata = Table.grid(padding=(0, 2))
        metadata.add_column(style=TEXT_MUTED_DEEP, width=10)
        metadata.add_column()
        for label, value in detail.metadata_rows:
            metadata.add_row(label, value)

        scope = Table.grid(padding=(0, 2))
        scope.add_column(style=TEXT_MUTED_DEEP, width=10)
        scope.add_column()
        for label, value in detail.scope_rows:
            scope.add_row(label, value)

        actions = Text()
        for index, (key, action) in enumerate(detail.action_hints):
            if index:
                actions.append("   ", style=TEXT_MUTED_DEEP)
            actions.append_text(key_hint(key, action))
        self.update(
            Group(
                status_badge(detail.status),
                Text(""),
                metadata,
                Text(""),
                title("Description"),
                Text(detail.description),
                Text(""),
                title("Scope"),
                scope,
                Text(""),
                title("Actions"),
                actions,
            )
        )
