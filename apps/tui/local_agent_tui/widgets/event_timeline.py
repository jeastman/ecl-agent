from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.console import Group
from rich.markup import escape
from rich.text import Text

from ..store.selectors import TimelineEventViewModel, TimelineGroupViewModel
from ..theme.colors import ACCENT, DANGER, SUCCESS, TEXT_MUTED_DEEP, TEXT_SECONDARY, WARNING
from ..theme.empty_states import render_empty_state

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
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_event_signature: tuple[str, int] | None = None
        self._show_new_events_indicator = False

    def update_timeline(self, model: TimelineGroupViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Event Timeline"
        subtitle = f"Filter: {escape(model.filter_label)}"
        if model.search_query:
            subtitle = f"{subtitle} | Search: {escape(model.search_query)}"
        is_at_bottom = self._is_at_bottom()
        signature = _timeline_signature(model)
        if (
            self._last_event_signature is not None
            and signature != self._last_event_signature
            and not is_at_bottom
        ):
            self._show_new_events_indicator = True
        elif is_at_bottom:
            self._show_new_events_indicator = False
        self._last_event_signature = signature
        if self._show_new_events_indicator:
            subtitle = f"{subtitle} | \N{DOWNWARDS ARROW} New events"
        self.border_subtitle = subtitle
        if not model.events:
            self.update(render_empty_state("events"))
            return
        self.update(Group(*[_render_event_card(event) for event in model.events]))
        if is_at_bottom:
            self.jump_to_latest()

    def jump_to_latest(self) -> None:
        self._show_new_events_indicator = False
        self.scroll_end(animate=False, immediate=True)

    def is_showing_new_events_indicator(self) -> bool:
        return self._show_new_events_indicator

    def _is_at_bottom(self) -> bool:
        return self.max_scroll_y <= 0 or self.scroll_y >= max(self.max_scroll_y - 1, 0)


def _timeline_signature(model: TimelineGroupViewModel) -> tuple[str, int]:
    if not model.events:
        return ("", 0)
    last_event = model.events[-1]
    return (f"{last_event.timestamp}:{last_event.event_type}:{last_event.summary}", len(model.events))


def _render_event_card(event: TimelineEventViewModel) -> Text:
    lines: list[Text] = []
    header = Text()
    if event.show_priority_highlight and event.priority_label:
        header.append(f"{event.priority_label} ", style="reverse")
    header.append(event.timestamp_display, style=TEXT_MUTED_DEEP)
    header.append("  ")
    header.append(event.severity_label, style=f"bold {_severity_color(event.severity)}")
    header.append("  ")
    header.append(event.event_type, style="bold")
    if event.repeat_count > 1:
        header.append(f" ×{event.repeat_count}", style=TEXT_SECONDARY)
    if event.source_label:
        header.append("  ")
        header.append(event.source_label, style=TEXT_SECONDARY)
    lines.append(header)

    summary = Text()
    summary.append("         ")
    summary_text = event.summary
    if event.repeat_count > 1 and not summary_text.endswith("(repeated)"):
        summary_text = f"{summary_text} (repeated)"
    summary.append(summary_text)
    lines.append(summary)

    for index, detail in enumerate(event.detail_lines):
        detail_line = Text()
        detail_line.append("         ")
        detail_line.append("└─ " if index == len(event.detail_lines) - 1 else "├─ ", style=TEXT_SECONDARY)
        detail_line.append(detail, style=TEXT_SECONDARY)
        lines.append(detail_line)

    lines.append(Text(""))
    return Text("\n").join(lines[:-1])


def _severity_color(severity: str) -> str:
    return {
        "error": DANGER,
        "attention": WARNING,
        "success": SUCCESS,
    }.get(severity.lower(), ACCENT)


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
    header = TimelineEventViewModel(
        timestamp=timestamp,
        timestamp_display=timestamp,
        event_type=event_type,
        severity_label={"error": "ERR ", "attention": "ATTN", "success": " OK "}.get(
            severity.lower(),
            "INFO",
        ),
        summary=summary,
        severity=severity,
        detail_lines=[],
        repeat_count=repeat_count,
        source_label=source_name,
        show_priority_highlight=highlight,
        priority_label=highlight_label,
    )
    return _render_event_card(header)
