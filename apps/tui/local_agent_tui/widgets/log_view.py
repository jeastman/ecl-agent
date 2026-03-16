from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.selectors import LogViewModel
from ..theme.colors import ACCENT, DANGER, SUCCESS, WARNING

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import VerticalScroll
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import VerticalScroll
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        VerticalScroll = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class LogViewWidget(VerticalScroll):  # type: ignore[misc]
    can_focus = True

    def compose(self) -> ComposeResult:
        yield Static(id="task-detail-logs-body")

    def update_logs(self, model: LogViewModel, *, visible: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Logs"
        self.set_class(not visible, "-hidden")
        if not visible:
            return
        body = self.query_one("#task-detail-logs-body", Static)
        if not model.lines:
            body.update("No logs captured yet.")
            self.scroll_to(y=0, animate=False, immediate=True)
            return
        should_tail = self.scroll_y >= max(0.0, self.max_scroll_y - 1)
        body.update(
            "\n".join(
                f"{line.timestamp} [{_level_color(line.level)}]{line.level:<7}[/] "
                f"{line.source_name or 'runtime'}  {'[reverse]' if line.is_highlighted else ''}"
                f"{line.message}{'[/reverse]' if line.is_highlighted else ''}"
                for line in model.lines
            )
        )
        if should_tail:
            self.scroll_to_end()

    def scroll_line(self, delta: int) -> None:
        next_y = max(0.0, min(self.max_scroll_y, self.scroll_y + delta))
        self.scroll_to(y=next_y, animate=False, immediate=True)

    def scroll_to_home(self) -> None:
        self.scroll_to(y=0, animate=False, immediate=True)

    def scroll_to_end(self) -> None:
        self.scroll_to(y=self.max_scroll_y, animate=False, immediate=True)


def _level_color(level: str) -> str:
    return {
        "ERROR": DANGER,
        "ATTENTION": WARNING,
        "SUCCESS": SUCCESS,
    }.get(level.upper(), ACCENT)
