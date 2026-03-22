from __future__ import annotations

from typing import Any

from rich.console import Group
from rich.markup import escape
from rich.syntax import Syntax
from rich.text import Text

from ..compat import ComposeResult, Container, ListView, Screen, Static, Vertical, _TEXTUAL_IMPORT_ERROR
from ..renderables import text
from ..store.app_state import AppState
from ..store.selectors import (
    footer_hints,
    memory_entry_items,
    memory_group_summary,
    memory_scope_groups,
    selected_memory_detail,
)
from ..widgets.loading import loading_renderable
from ..widgets.memory_entry_list import MemoryEntryListWidget, MemoryEntryRow
from ..widgets.memory_group_list import MemoryGroupListWidget, MemoryGroupRow
from ..widgets.status_bar import StatusBar
from ..widgets.toast import ToastRack
from ..theme.colors import STATUS_DANGER, TEXT_SECONDARY


class MemoryScreen(Screen):  # type: ignore[misc]
    PANE_ORDER = ["memory_groups", "memory_entries"]

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
            ToastRack(id="toast-rack"),
            id="memory-screen-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        if state.memory_request_status == "loading":
            self.query_one(MemoryGroupListWidget).show_loading(
                "Loading scopes...",
                focused=state.focused_pane == "memory_groups",
            )
            self.query_one(MemoryEntryListWidget).show_loading(
                "Loading entries...",
                focused=state.focused_pane == "memory_entries",
            )
            summary = self.query_one("#memory-screen-group-summary", Static)
            summary.border_title = "Selected Scope"
            summary.update(loading_renderable("Loading memory summary...", skeleton_lines=2))
            detail = self.query_one("#memory-screen-detail", Static)
            detail.border_title = "Memory Inspector"
            detail.update(loading_renderable("Loading memory details...", skeleton_lines=5))
            footer = footer_hints(state, contextual=True)
            footer.append("\nMemory inspector is read-only.", style=TEXT_SECONDARY)
            if self._last_footer != footer.plain:
                self.query_one("#memory-screen-footer", Static).update(footer)
                self._last_footer = footer.plain
            return
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
            summary.update(text(summary_text))
            self._last_summary = summary_text
        detail_model = selected_memory_detail(state)
        detail = self.query_one("#memory-screen-detail", Static)
        detail.border_title = escape(detail_model.title)
        detail_signature = (
            detail_model.title,
            detail_model.summary,
            detail_model.content,
            detail_model.provenance,
        )
        if self._last_detail_signature != detail_signature:
            detail.update(_render_memory_detail(detail_model))
            self._last_detail_signature = detail_signature
        footer = footer_hints(state, contextual=True)
        footer.append("\nMemory inspector is read-only.", style=TEXT_SECONDARY)
        if state.memory_request_error:
            footer.append(f"\n{escape(state.memory_request_error)}", style=STATUS_DANGER)
        if self._last_footer != footer.plain:
            self.query_one("#memory-screen-footer", Static).update(footer)
            self._last_footer = footer.plain

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


def _render_memory_detail(model: Any) -> Group:
    metadata_lines = [Text(f"{label}: {value}") for label, value in model.metadata_rows]
    content = (
        Syntax(model.content, model.content_format, word_wrap=True, line_numbers=False)
        if model.content_format != "text"
        else Text(model.content)
    )
    provenance = (
        Syntax(model.provenance, model.provenance_format, word_wrap=True, line_numbers=False)
        if model.provenance_format != "text"
        else Text(model.provenance)
    )
    return Group(
        Text(model.summary),
        Text(""),
        Text("Content", style="bold"),
        content,
        Text(""),
        Text("Metadata", style="bold"),
        *metadata_lines,
        Text(""),
        Text("Provenance", style="bold"),
        provenance,
    )
