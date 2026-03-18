from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.text import Text

from ..store.selectors import ArtifactPanelItemViewModel

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


class ArtifactPanelWidget(Static):  # type: ignore[misc]
    def update_artifacts(self, items: list[ArtifactPanelItemViewModel]) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Artifacts"
        if not items:
            self.update("No artifacts for this task.")
            return
        self.update(
            Group(
                *(
                    Text.assemble(
                        f"{'>' if item.is_selected else ' '} {item.display_name}\n"
                        f"{item.content_type}  {item.logical_path}"
                    )
                    for item in items
                )
            )
        )
