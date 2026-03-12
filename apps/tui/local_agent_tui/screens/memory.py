from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import (
    footer_hints,
    memory_entry_items,
    memory_group_summary,
    memory_scope_groups,
    selected_memory_detail,
)
from ..widgets.memory_entry_list import MemoryEntryListWidget, MemoryEntryRow
from ..widgets.memory_group_list import MemoryGroupListWidget, MemoryGroupRow
from ..widgets.status_bar import StatusBar

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container, Vertical
    from textual.screen import Screen
    from textual.widgets import ListView, Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container, Vertical
        from textual.screen import Screen
        from textual.widgets import ListView, Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        Vertical = cast(Any, object)
        Screen = cast(Any, object)
        ListView = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class MemoryScreen(Screen):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_summary: str | None = None
        self._last_detail_signature: tuple[str, ...] | None = None
        self._last_footer: str | None = None

    def compose(self) -> ComposeResult:
        yield Container(
            StatusBar(id="status-bar"),
            Container(
                MemoryGroupListWidget(id="memory-screen-groups"),
                Vertical(
                    Static(id="memory-screen-group-summary"),
                    MemoryEntryListWidget(id="memory-screen-entries"),
                    Static(id="memory-screen-detail"),
                    id="memory-screen-side",
                ),
                id="memory-screen-main",
            ),
            Static(id="memory-screen-footer"),
            id="memory-screen-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        self.query_one(MemoryGroupListWidget).update_groups(
            memory_scope_groups(state),
            focused=state.focused_pane == "memory_groups",
        )
        self.query_one(MemoryEntryListWidget).update_entries(
            memory_entry_items(state),
            focused=state.focused_pane == "memory_entries",
        )
        summary = self.query_one("#memory-screen-group-summary", Static)
        summary.border_title = "Selected Scope"
        summary_text = memory_group_summary(state)
        if self._last_summary != summary_text:
            summary.update(summary_text)
            self._last_summary = summary_text
        detail_model = selected_memory_detail(state)
        detail = self.query_one("#memory-screen-detail", Static)
        detail.border_title = detail_model.title
        detail_text = "\n".join(
            [
                detail_model.summary,
                "",
                "Content",
                detail_model.content,
                "",
                "Metadata",
                f"Scope: {detail_model.raw_scope or 'n/a'}",
                f"Namespace: {detail_model.namespace or 'n/a'}",
                f"Source Run: {detail_model.source_run}",
                f"Confidence: {detail_model.confidence}",
                f"Created: {detail_model.created_at or 'n/a'}",
                f"Updated: {detail_model.updated_at or 'n/a'}",
                "Provenance",
                detail_model.provenance,
            ]
        )
        detail_signature = (detail_model.title, detail_text)
        if self._last_detail_signature != detail_signature:
            detail.update(detail_text.strip())
            self._last_detail_signature = detail_signature
        footer = "   ".join(footer_hints(state))
        footer = f"{footer}\nMemory inspector is read-only."
        if state.memory_request_error:
            footer = f"{footer}\n{state.memory_request_error}"
        if self._last_footer != footer:
            self.query_one("#memory-screen-footer", Static).update(footer)
            self._last_footer = footer

    def on_list_view_highlighted(self, message: ListView.Highlighted) -> None:
        if message.list_view.id == "memory-screen-groups" and isinstance(
            message.item, MemoryGroupRow
        ):
            self.app.handle_memory_group_selected(message.item.group_id)  # type: ignore[attr-defined]
            return
        if message.list_view.id == "memory-screen-entries" and isinstance(
            message.item, MemoryEntryRow
        ):
            self.app.handle_memory_entry_selected(message.item.memory_id)  # type: ignore[attr-defined]
