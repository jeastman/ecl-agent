from __future__ import annotations

from typing import Any

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from ..compat import ComposeResult, Static, VerticalScroll, _TEXTUAL_IMPORT_ERROR
from ..store.selectors import ConfigDetailViewModel
from .loading import loading_renderable


class ConfigDetailWidget(VerticalScroll):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_signature: tuple[str, str, str, str] | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="config-screen-detail-body")

    def update_detail(self, model: ConfigDetailViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        signature = (model.title, model.status, model.summary, model.body)
        if self._last_signature == signature:
            return
        self.border_title = model.title
        summary = model.summary
        if model.redaction_count:
            summary = f"{summary}  [REDACTED x{model.redaction_count}]"
        body_renderable = (
            Syntax(model.body, model.body_format, word_wrap=True, line_numbers=False)
            if model.body_format != "text"
            else Text(model.body)
        )
        self.query_one("#config-screen-detail-body", Static).update(
            Group(
                Text(f"Status: {model.status.upper()}"),
                Text(""),
                Text(summary),
                Text(""),
                body_renderable,
            )
        )
        self._last_signature = signature

    def show_loading(self, label: str) -> None:
        self.border_title = "Config Viewer"
        self.query_one("#config-screen-detail-body", Static).update(
            loading_renderable(label, skeleton_lines=4)
        )
        self._last_signature = None
