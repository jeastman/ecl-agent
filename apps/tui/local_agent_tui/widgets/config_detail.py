from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from ..store.selectors import ConfigDetailViewModel
from .loading import loading_renderable

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


class ConfigDetailWidget(Static):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_signature: tuple[str, str, str, str] | None = None

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
        self.update(
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
        self.update(loading_renderable(label, skeleton_lines=4))
        self._last_signature = None
