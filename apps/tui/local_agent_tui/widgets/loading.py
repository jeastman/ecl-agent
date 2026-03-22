from __future__ import annotations

from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text

from ..compat import Static, _TEXTUAL_IMPORT_ERROR
from ..theme.colors import STATUS_INFO, TEXT_MUTED_DEEP, TEXT_SECONDARY


_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_SKELETON_WIDTHS = (36, 28, 32, 20, 24)


def loading_renderable(
    label: str,
    *,
    frame: int = 0,
    compact: bool = False,
    skeleton_lines: int = 0,
    progress_label: str | None = None,
) -> RenderableType:
    spinner = Text()
    spinner.append(_SPINNER_FRAMES[frame % len(_SPINNER_FRAMES)], style=f"bold {STATUS_INFO}")
    spinner.append(" ")
    spinner.append(label, style=TEXT_SECONDARY)
    if compact and skeleton_lines <= 0:
        return spinner
    skeleton = [spinner, Text("")]
    if progress_label:
        skeleton.append(Text(progress_label, style=TEXT_SECONDARY))
        skeleton.append(Text(""))
    for index in range(max(2, skeleton_lines)):
        width = _SKELETON_WIDTHS[index % len(_SKELETON_WIDTHS)]
        highlight = (frame // 2 + index) % 3 == 0
        style = TEXT_SECONDARY if highlight else TEXT_MUTED_DEEP
        skeleton.append(Text("▇" * width, style=style))
    return Group(*skeleton)


class LoadingWidget(Static):  # type: ignore[misc]
    def __init__(
        self,
        label: str = "Loading...",
        *,
        compact: bool = False,
        skeleton_lines: int = 3,
        progress_label: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__("", **kwargs)
        self._label = label
        self._compact = compact
        self._skeleton_lines = skeleton_lines
        self._progress_label = progress_label
        self._frame = 0

    def on_mount(self) -> None:  # pragma: no cover
        self.set_interval(0.12, self._advance)
        self._render_loading()

    def set_label(self, label: str) -> None:
        self._label = label
        self._render_loading()

    def set_progress_label(self, progress_label: str | None) -> None:
        self._progress_label = progress_label
        self._render_loading()

    def _advance(self) -> None:  # pragma: no cover
        self._frame += 1
        self._render_loading()

    def _render_loading(self) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.update(
            loading_renderable(
                self._label,
                frame=self._frame,
                compact=self._compact,
                skeleton_lines=self._skeleton_lines,
                progress_label=self._progress_label,
            )
        )
