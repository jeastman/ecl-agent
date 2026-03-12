from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
    def update_detail(self, model: ConfigDetailViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = model.title
        self.update(
            "\n".join(
                [
                    f"Status: {model.status}",
                    "",
                    model.summary,
                    "",
                    model.body,
                ]
            ).strip()
        )
