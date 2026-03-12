from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
        if not model.events:
            self.update("No events yet.")
            return
        self.update(
            "\n".join(
                _render_event_line(
                    timestamp=event.timestamp,
                    severity=event.severity,
                    summary=event.summary,
                    repeat_count=event.repeat_count,
                )
                for event in model.events
            )
        )


def _render_event_line(
    *,
    timestamp: str,
    severity: str,
    summary: str,
    repeat_count: int,
) -> str:
    marker, color = {
        "error": ("ERR", DANGER),
        "attention": ("ATTN", WARNING),
        "success": ("OK", SUCCESS),
    }.get(severity, ("INFO", ACCENT))
    suffix = f" x{repeat_count}" if repeat_count > 1 else ""
    return f"[{color}]{timestamp} [{marker}][/] {summary}{suffix}"
