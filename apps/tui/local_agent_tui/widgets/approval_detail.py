from __future__ import annotations

from rich.console import Group
from rich.table import Table
from rich.text import Text

from ..compat import Static, _TEXTUAL_IMPORT_ERROR
from ..store.selectors import ApprovalDetailViewModel
from ..theme.colors import DANGER, TEXT_MUTED_DEEP, WARNING
from ..theme.typography import key_hint, status_badge, title
from ._dirty import DirtyCheckMixin


class ApprovalDetailWidget(DirtyCheckMixin, Static):  # type: ignore[misc]
    def update_detail(self, detail: ApprovalDetailViewModel | None) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Request Details"
        if not self._should_render(detail):
            return
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
