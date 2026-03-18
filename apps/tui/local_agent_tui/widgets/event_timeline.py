from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.markup import escape
from rich.text import Text

from ..store.selectors import TimelineGroupViewModel
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


class EventTimelineWidget(Static):  # type: ignore[misc]
    def update_timeline(self, model: TimelineGroupViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Event Timeline"
        subtitle = f"Filter: {escape(model.filter_label)}"
        if model.search_query:
            subtitle = f"{subtitle} | Search: {escape(model.search_query)}"
        self.border_subtitle = subtitle
        if not model.events:
            self.update("No events yet.")
            return
        self.update(
            Group(
                *(
                    _render_event_line(
                        timestamp=event.timestamp,
                        event_type=event.event_type,
                        severity=event.severity,
                        summary=event.summary,
                        repeat_count=event.repeat_count,
                        source_name=event.source_name,
                        highlight=event.highlight,
                        highlight_label=event.highlight_label,
                    )
                    for event in model.events
                )
            )
        )


def _render_event_line(
    *,
    timestamp: str,
    event_type: str,
    severity: str,
    summary: str,
    repeat_count: int,
    source_name: str | None,
    highlight: bool,
    highlight_label: str | None,
) -> Text:
    marker, color = {
        "error": ("ERR", DANGER),
        "attention": ("ATTN", WARNING),
        "success": ("OK", SUCCESS),
    }.get(severity, ("INFO", ACCENT))
    source = f" {source_name}" if source_name else ""
    collapsed = (
        f"{event_type}{source} (x{repeat_count})"
        if repeat_count > 1
        else f"{event_type}{source}"
    )
    line = Text()
    if highlight and highlight_label:
        line.append(f"{highlight_label} ", style="reverse")
    line.append(timestamp, style=color)
    line.append(f" [{marker}] ")
    line.append(collapsed)
    line.append("  ")
    line.append(summary)
    return line
