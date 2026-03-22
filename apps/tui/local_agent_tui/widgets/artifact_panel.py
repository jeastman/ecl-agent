from __future__ import annotations

from rich.console import Group
from rich.text import Text

from ..compat import Static, _TEXTUAL_IMPORT_ERROR
from ..store.selectors import ArtifactPanelItemViewModel
from ._dirty import DirtyCheckMixin


class ArtifactPanelWidget(DirtyCheckMixin, Static):  # type: ignore[misc]
    def update_artifacts(self, items: list[ArtifactPanelItemViewModel]) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Artifacts"
        if not self._should_render(items):
            return
        if not items:
            self.set_class(True, "-empty-panel")
            self.update("No artifacts for this task.")
            return
        self.set_class(False, "-empty-panel")
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
