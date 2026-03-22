from __future__ import annotations

from typing import Any

from rich.console import Group
from rich.text import Text

from ..compat import ComposeResult, Static, VerticalScroll, _TEXTUAL_IMPORT_ERROR
from ..store.selectors import LogViewModel
from ..theme.colors import ACCENT, DANGER, SUCCESS, WARNING
from ._dirty import DirtyCheckMixin


class LogViewWidget(DirtyCheckMixin, VerticalScroll):  # type: ignore[misc]
    can_focus = True

    def compose(self) -> ComposeResult:
        yield Static(id="task-detail-logs-body")

    def update_logs(self, model: LogViewModel, *, visible: bool) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        if not self._should_render((model, visible)):
            return
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
        body.update(Group(*(_render_log_line(line) for line in model.lines)))
        if should_tail:
            self.scroll_to_end()

    def scroll_line(self, delta: int) -> None:
        next_y = max(0.0, min(self.max_scroll_y, self.scroll_y + delta))
        self.scroll_to(y=next_y, animate=False, immediate=True)

    def scroll_page(self, delta: int) -> None:
        step = max(1, int(getattr(self, "content_size", None).height or 10) // 2)
        self.scroll_line(step * delta)

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


def _render_log_line(line: Any) -> Text:
    rendered = Text()
    if line.is_highlighted:
        rendered.stylize("reverse")
    rendered.append(line.timestamp)
    rendered.append(" ")
    rendered.append(f"{line.level:<7}", style=_level_color(line.level))
    rendered.append(" ")
    rendered.append(line.source_name or "runtime")
    rendered.append("  ")
    rendered.append(line.message)
    return rendered
