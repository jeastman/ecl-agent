from __future__ import annotations

from typing import Any

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from ..compat import ComposeResult, Static, VerticalScroll, _TEXTUAL_IMPORT_ERROR
from ..store.selectors import ArtifactPreviewViewModel
from .loading import loading_renderable
from ._dirty import DirtyCheckMixin


class ArtifactPreviewWidget(DirtyCheckMixin, VerticalScroll):  # type: ignore[misc]
    can_focus = True

    def compose(self) -> ComposeResult:
        yield Static(id="artifact-preview-meta")
        yield Static(id="artifact-preview-body")

    def update_preview(self, model: ArtifactPreviewViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        if not self._should_render(model):
            return
        self.border_title = f"{model.icon} {model.title}".strip()
        self.query_one("#artifact-preview-meta", Static).update(Text(model.metadata_summary))
        body_widget = self.query_one("#artifact-preview-body", Static)
        if model.render_as_markdown:
            body_widget.update(Text(model.body))
        elif model.status == "loading":
            body_widget.update(loading_renderable("Loading preview...", skeleton_lines=6))
        else:
            body_widget.update(
                Syntax(model.body or "No preview available.", model.render_language, word_wrap=True, line_numbers=False)
            )
        self.scroll_home(animate=False)

    def show_loading(self, label: str) -> None:
        self._reset_render_cache()
        self.border_title = "Preview"
        self.query_one("#artifact-preview-meta", Static).update(
            loading_renderable(label, skeleton_lines=2)
        )
        self.query_one("#artifact-preview-body", Static).update(
            loading_renderable("Loading preview...", skeleton_lines=6)
        )
        self.scroll_home(animate=False)
