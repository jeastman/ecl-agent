from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.text import Text

from ..store.selectors import ArtifactPreviewViewModel

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import VerticalScroll
    from textual.widgets import Markdown, Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import VerticalScroll
        from textual.widgets import Markdown, Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        VerticalScroll = cast(Any, object)
        Markdown = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class ArtifactPreviewWidget(VerticalScroll):  # type: ignore[misc]
    can_focus = True

    def compose(self) -> ComposeResult:
        yield Static(id="artifact-preview-meta")
        yield Markdown("", id="artifact-preview-body")

    def update_preview(self, model: ArtifactPreviewViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = model.title
        self.query_one("#artifact-preview-meta", Static).update(
            Group(
                Text(f"Status: {model.status}"),
                Text(f"Type: {model.content_type or 'unknown'}"),
                Text(f"Action: {model.open_label}"),
                Text(f"External Open: {'yes' if model.external_open_supported else 'no'}"),
                Text(""),
            )
        )
        body = model.body if model.render_as_markdown else _as_markdown_code_block(model.body)
        self.query_one("#artifact-preview-body", Markdown).update(body)
        self.scroll_home(animate=False)


def _as_markdown_code_block(text: str) -> str:
    stripped = text.rstrip()
    if not stripped:
        return "_No preview available._"
    return f"```text\n{stripped}\n```"
