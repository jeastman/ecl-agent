from __future__ import annotations

from rich.markup import escape

from ..compat import ComposeResult, Container, ListView, Screen, Static, _TEXTUAL_IMPORT_ERROR
from ..store.app_state import AppState
from ..store.selectors import (
    artifact_browser_rows,
    artifact_browser_toolbar,
    footer_hints,
    selected_artifact_preview,
)
from ..widgets.artifact_preview import ArtifactPreviewWidget
from ..widgets.artifact_table import ArtifactTableRow, ArtifactTableWidget
from ..widgets.status_bar import StatusBar
from ..widgets.toast import ToastRack
from ..theme.colors import TEXT_SECONDARY


class ArtifactsScreen(Screen):  # type: ignore[misc]
    PANE_ORDER = ["artifacts_table", "artifact_preview"]

    def compose(self) -> ComposeResult:
        yield Container(
            StatusBar(id="status-bar"),
            Container(
                ArtifactTableWidget(id="artifacts-screen-table"),
                ArtifactPreviewWidget(id="artifacts-screen-preview"),
                id="artifacts-screen-main",
            ),
            Static(id="artifacts-screen-footer"),
            ToastRack(id="toast-rack"),
            id="artifacts-screen-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        table_focused = state.focused_pane == "artifacts_table"
        toolbar = artifact_browser_toolbar(state)
        if state.artifacts_request_status == "loading":
            self.query_one(ArtifactTableWidget).show_loading(
                "Refreshing artifacts...",
                focused=table_focused,
                group_by=toolbar.group_by,
            )
            preview_widget = self.query_one(ArtifactPreviewWidget)
            preview_widget.set_class(state.focused_pane == "artifact_preview", "-focused-pane")
            preview_widget.show_loading("Loading preview context...")
            footer = footer_hints(state, contextual=True)
            footer.append(
                f"\nGrouping: {escape(toolbar.group_by)}   Artifacts: {toolbar.total_count}",
                style=TEXT_SECONDARY,
            )
            self.query_one("#artifacts-screen-footer", Static).update(footer)
            return
        self.query_one(ArtifactTableWidget).update_artifacts(
            artifact_browser_rows(state),
            focused=table_focused,
            group_by=toolbar.group_by,
        )
        preview_widget = self.query_one(ArtifactPreviewWidget)
        preview_widget.set_class(state.focused_pane == "artifact_preview", "-focused-pane")
        preview_widget.update_preview(selected_artifact_preview(state))
        footer = footer_hints(state, contextual=True)
        footer.append(
            f"\nGrouping: {escape(toolbar.group_by)}   Artifacts: {toolbar.total_count}",
            style=TEXT_SECONDARY,
        )
        self.query_one("#artifacts-screen-footer", Static).update(footer)

    def on_list_view_highlighted(self, message: ListView.Highlighted) -> None:
        if message.list_view.id != "artifacts-screen-table":
            return
        item = message.item
        if isinstance(item, ArtifactTableRow):
            self.app.handle_artifact_browser_selected(item.artifact_id)  # type: ignore[attr-defined]

    def on_list_view_selected(self, message: ListView.Selected) -> None:
        if message.list_view.id != "artifacts-screen-table":
            return
        self.app.action_open_task()  # type: ignore[attr-defined]
