from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..renderables import block, metadata_line, text
from ..store.selectors import ConfigDetailViewModel

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
        self.update(
            block(
                [
                    metadata_line([("Status", model.status)]),
                    "",
                    text(model.summary),
                    "",
                    text(model.body),
                ]
            )
        )
        self._last_signature = signature
