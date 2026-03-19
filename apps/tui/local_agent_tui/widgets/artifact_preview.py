from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from ..store.selectors import ArtifactPreviewViewModel
from .loading import loading_renderable

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import VerticalScroll
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import VerticalScroll
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        VerticalScroll = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class ArtifactPreviewWidget(VerticalScroll):  # type: ignore[misc]
    can_focus = True

    def compose(self) -> ComposeResult:
        yield Static(id="artifact-preview-meta")
        yield Static(id="artifact-preview-body")

    def update_preview(self, model: ArtifactPreviewViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
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
        self.border_title = "Preview"
        self.query_one("#artifact-preview-meta", Static).update(
            loading_renderable(label, skeleton_lines=2)
        )
        self.query_one("#artifact-preview-body", Static).update(
            loading_renderable("Loading preview...", skeleton_lines=6)
        )
        self.scroll_home(animate=False)
