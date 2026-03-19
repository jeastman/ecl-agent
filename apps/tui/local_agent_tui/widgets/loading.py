from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group, RenderableType
from rich.text import Text

from ..theme.colors import STATUS_INFO, TEXT_MUTED_DEEP, TEXT_SECONDARY

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


_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


def loading_renderable(
    label: str,
    *,
    frame: int = 0,
    compact: bool = False,
    skeleton_lines: int = 0,
) -> RenderableType:
    spinner = Text()
    spinner.append(_SPINNER_FRAMES[frame % len(_SPINNER_FRAMES)], style=f"bold {STATUS_INFO}")
    spinner.append(" ")
    spinner.append(label, style=TEXT_SECONDARY)
    if compact and skeleton_lines <= 0:
        return spinner
    skeleton = [spinner, Text("")]
    for index in range(max(2, skeleton_lines)):
        width = 28 if index % 2 == 0 else 20
        skeleton.append(Text("▇" * width, style=TEXT_MUTED_DEEP))
    return Group(*skeleton)


class LoadingWidget(Static):  # type: ignore[misc]
    def __init__(
        self,
        label: str = "Loading...",
        *,
        compact: bool = False,
        skeleton_lines: int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__("", **kwargs)
        self._label = label
        self._compact = compact
        self._skeleton_lines = skeleton_lines
        self._frame = 0

    def on_mount(self) -> None:  # pragma: no cover
        self.set_interval(0.12, self._advance)
        self._render_loading()

    def set_label(self, label: str) -> None:
        self._label = label
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
            )
        )
