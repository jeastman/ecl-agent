from __future__ import annotations

from typing import Any

from rich.console import Group
from rich.markup import escape
from rich.text import Text

from ..compat import ComposeResult, Static, VerticalScroll, _TEXTUAL_IMPORT_ERROR
from ..store.selectors import TimelineEventViewModel, TimelineGroupViewModel
from ..theme.colors import ACCENT, DANGER, SUCCESS, TEXT_MUTED_DEEP, TEXT_SECONDARY, WARNING
from ..theme.empty_states import render_empty_state
from ._dirty import DirtyCheckMixin


class EventTimelineWidget(DirtyCheckMixin, VerticalScroll):  # type: ignore[misc]
    can_focus = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_event_signature: tuple[str, int] | None = None
        self._last_view_state: tuple[str, str] | None = None
        self._show_new_events_indicator = False
        self._is_tailing = True

    def compose(self) -> ComposeResult:
        yield Static(id="task-detail-timeline-body")

    def update_timeline(self, model: TimelineGroupViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Event Timeline"
        subtitle = f"Filter: {escape(model.filter_label)}"
        if model.search_query:
            subtitle = f"{subtitle} | Search: {escape(model.search_query)}"
        signature = _timeline_signature(model)
        view_state = (model.filter_label, model.search_query)
        body = self.query_one("#task-detail-timeline-body", Static)
        should_render_body = self._should_render(model, attr_name="_last_rendered_model")
        if view_state != self._last_view_state:
            self._show_new_events_indicator = False
        elif self._is_tailing:
            self._show_new_events_indicator = False
        elif self._last_event_signature is not None and signature != self._last_event_signature:
            self._show_new_events_indicator = True
        self._last_event_signature = signature
        self._last_view_state = view_state
        if self._show_new_events_indicator:
            subtitle = f"{subtitle} | \N{DOWNWARDS ARROW} New events"
        self.border_subtitle = subtitle
        if not model.events:
            if should_render_body:
                body.update(render_empty_state("events"))
            self._show_new_events_indicator = False
            self._is_tailing = True
            self.scroll_to_home()
            return
        if should_render_body:
            body.update(Group(*[_render_event_card(event) for event in model.events]))
        if self._is_tailing and should_render_body:
            self._schedule_jump_to_latest()

    def scroll_line(self, delta: int) -> None:
        next_y = max(0.0, min(self.max_scroll_y, self.scroll_y + delta))
        self.scroll_to(y=next_y, animate=False, immediate=True)
        if delta < 0:
            self._is_tailing = False
        if self.is_at_bottom():
            self._is_tailing = True
            self._show_new_events_indicator = False

    def scroll_page(self, delta: int) -> None:
        step = max(1, int(getattr(self, "content_size", None).height or 10) // 2)
        self.scroll_line(step * delta)

    def scroll_to_home(self) -> None:
        self._is_tailing = False
        self.scroll_home(animate=False)

    def scroll_to_end(self) -> None:
        self._is_tailing = True
        self.scroll_end(animate=False, immediate=True)

    def jump_to_latest(self) -> None:
        self._is_tailing = True
        self._show_new_events_indicator = False
        self._schedule_jump_to_latest()

    def is_showing_new_events_indicator(self) -> bool:
        return self._show_new_events_indicator

    def is_at_bottom(self) -> bool:
        return self._is_tailing or self._viewport_is_at_bottom()

    def _viewport_is_at_bottom(self) -> bool:
        return self.max_scroll_y > 0 and self.scroll_y >= max(self.max_scroll_y - 1, 0)

    def _schedule_jump_to_latest(self) -> None:
        self.call_after_refresh(self._scroll_to_latest_after_refresh)

    def _scroll_to_latest_after_refresh(self) -> None:
        self.scroll_to_end()


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
