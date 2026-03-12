from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.selectors import LogViewModel
from ..theme.colors import ACCENT, DANGER, SUCCESS, WARNING

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


class LogViewWidget(Static):  # type: ignore[misc]
    def update_logs(self, model: LogViewModel, *, visible: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Logs"
        self.set_class(not visible, "-hidden")
        if not visible:
            return
        if not model.lines:
            self.update("No logs captured yet.")
            return
        self.update(
            "\n".join(
                f"{line.timestamp} [{_level_color(line.level)}]{line.level:<7}[/] "
                f"{line.source_name or 'runtime'}  {'[reverse]' if line.is_highlighted else ''}"
                f"{line.message}{'[/reverse]' if line.is_highlighted else ''}"
                for line in model.lines
            )
        )


def _level_color(level: str) -> str:
    return {
        "ERROR": DANGER,
        "ATTENTION": WARNING,
        "SUCCESS": SUCCESS,
    }.get(level.upper(), ACCENT)
