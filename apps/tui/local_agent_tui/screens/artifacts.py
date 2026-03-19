from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
from ..theme.colors import STATUS_DANGER, TEXT_SECONDARY

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.screen import Screen
    from textual.widgets import ListView, Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container
        from textual.screen import Screen
        from textual.widgets import ListView, Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        Screen = cast(Any, object)
        ListView = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class ArtifactsScreen(Screen):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            StatusBar(id="status-bar"),
            Container(
                ArtifactTableWidget(id="artifacts-screen-table"),
                ArtifactPreviewWidget(id="artifacts-screen-preview"),
                id="artifacts-screen-main",
            ),
            Static(id="artifacts-screen-footer", markup=False),
            id="artifacts-screen-root",
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.query_one(StatusBar).update_from_state(state)
        toolbar = artifact_browser_toolbar(state)
        self.query_one(ArtifactTableWidget).update_artifacts(
            artifact_browser_rows(state),
            focused=True,
            group_by=toolbar.group_by,
        )
        self.query_one(ArtifactPreviewWidget).update_preview(selected_artifact_preview(state))
        footer = footer_hints(state)
        footer.append(
            f"\nGrouping: {escape(toolbar.group_by)}   Artifacts: {toolbar.total_count}",
            style=TEXT_SECONDARY,
        )
        if state.artifact_action_feedback:
            footer.append(f"\n{escape(state.artifact_action_feedback)}", style=STATUS_DANGER)
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
