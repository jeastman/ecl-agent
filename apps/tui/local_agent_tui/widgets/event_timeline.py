from __future__ import annotations

from typing import Any

from rich.cells import cell_len
from rich.console import Console
from rich.console import Group
from rich.markup import escape
from rich.text import Text

from ..compat import ComposeResult, Static, VerticalScroll, _TEXTUAL_IMPORT_ERROR
from ..store.selectors import TimelineEventViewModel, TimelineGroupViewModel
from ..theme.colors import DANGER, SEVERITY_INFO, SUCCESS, TEXT_MUTED_DEEP, TEXT_SECONDARY, WARNING
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
            available_width = max(24, (self.content_size.width or 80) - 2)
            body.update(Group(*[_render_event_card(event, width=available_width) for event in model.events]))
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


_WRAP_CONSOLE = Console(width=80, color_system=None, legacy_windows=False)


def _render_event_card(event: TimelineEventViewModel, *, width: int = 80) -> Text:
    lines: list[Text] = []
    header_content = Text()
    if event.show_priority_highlight and event.priority_label:
        header_content.append(f"{event.priority_label} ", style="reverse")
    header_content.append(
        _aligned_timestamp_display(
            event.timestamp_display,
            has_marker=event.show_priority_highlight and bool(event.priority_label),
        ),
        style=TEXT_MUTED_DEEP,
    )
    header_content.append("  ")
    header_content.append(event.severity_label, style=f"bold {_severity_color(event.severity)}")
    header_content.append("  ")
    header_content.append(f"{event.icon} ", style=_severity_color(event.severity))
    header_content.append(event.event_type, style="bold")
    if event.repeat_count > 1:
        header_content.append(f" ×{event.repeat_count}", style=TEXT_SECONDARY)
    if event.source_label:
        header_content.append("  ")
        header_content.append(event.source_label, style=TEXT_SECONDARY)
    header_prefix = _prefix_text(f"{event.severity_strip} ", _severity_color(event.severity))
    header_continuation = _prefix_text(
        f"{event.severity_strip}{' ' * (cell_len(header_prefix.plain) - 1)}",
        _severity_color(event.severity),
    )
    lines.extend(
        _wrap_prefixed_text(
            header_content,
            prefix_first=header_prefix,
            prefix_continuation=header_continuation,
            width=width,
        )
    )

    summary = Text()
    summary_text = event.summary
    if event.repeat_count > 1 and not summary_text.endswith("(repeated)"):
        summary_text = f"{summary_text} (repeated)"
    summary.append(summary_text)
    summary_prefix = _prefix_text(f"{event.severity_strip}       ", _severity_color(event.severity))
    lines.extend(
        _wrap_prefixed_text(
            summary,
            prefix_first=summary_prefix,
            prefix_continuation=summary_prefix,
            width=width,
        )
    )

    for index, detail in enumerate(event.collapsed_detail_lines):
        detail_line = Text(style=TEXT_SECONDARY)
        detail_line.append(
            "└─ " if index == len(event.collapsed_detail_lines) - 1 and not event.detail_overflow_count else "├─ ",
            style=TEXT_SECONDARY,
        )
        detail_line.append(detail, style=TEXT_SECONDARY)
        detail_prefix = _prefix_text(f"{event.severity_strip}       ", _severity_color(event.severity))
        detail_continuation = _prefix_text(
            f"{event.severity_strip}       {' ' * 3}",
            _severity_color(event.severity),
        )
        lines.extend(
            _wrap_prefixed_text(
                detail_line,
                prefix_first=detail_prefix,
                prefix_continuation=detail_continuation,
                width=width,
            )
        )
    if event.detail_overflow_count:
        overflow_line = Text(style=TEXT_MUTED_DEEP)
        overflow_line.append(f"... +{event.detail_overflow_count} more", style=TEXT_MUTED_DEEP)
        overflow_prefix = _prefix_text(f"{event.severity_strip}       ", _severity_color(event.severity))
        lines.extend(
            _wrap_prefixed_text(
                overflow_line,
                prefix_first=overflow_prefix,
                prefix_continuation=overflow_prefix,
                width=width,
            )
        )

    lines.append(Text(""))
    return Text("\n").join(lines[:-1])


def _prefix_text(text: str, style: str) -> Text:
    if not text:
        return Text()
    prefix = Text()
    prefix.append(text[0], style=style)
    if len(text) > 1:
        prefix.append(text[1:])
    return prefix


def _wrap_prefixed_text(
    content: Text,
    *,
    prefix_first: Text,
    prefix_continuation: Text,
    width: int,
) -> list[Text]:
    console = _WRAP_CONSOLE
    first_width = max(8, width - cell_len(prefix_first.plain))
    continuation_width = max(8, width - cell_len(prefix_continuation.plain))
    wrapped = content.wrap(
        console,
        first_width,
        overflow="fold",
        no_wrap=False,
    )
    if not wrapped:
        return [prefix_first.copy()]
    lines: list[Text] = []
    for index, line in enumerate(wrapped):
        prefix = prefix_first.copy() if index == 0 else prefix_continuation.copy()
        current_width = first_width if index == 0 else continuation_width
        if index > 0 and continuation_width != first_width:
            line = Text(line.plain, style=line.style)
            line.spans = list(line.spans)
            continuation_wrapped = line.wrap(console, current_width, overflow="fold", no_wrap=False)
            if continuation_wrapped:
                line = continuation_wrapped[0]
        prefix.append_text(line)
        lines.append(prefix)
    return lines


def _severity_color(severity: str) -> str:
    return {
        "error": DANGER,
        "attention": WARNING,
        "success": SUCCESS,
    }.get(severity.lower(), SEVERITY_INFO)


def _aligned_timestamp_display(timestamp_display: str, *, has_marker: bool = False) -> str:
    if has_marker:
        return timestamp_display
    return timestamp_display.rjust(8)


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
        collapsed_detail_lines=[],
        detail_overflow_count=0,
        repeat_count=repeat_count,
        source_label=source_name,
        show_priority_highlight=highlight,
        priority_label=highlight_label,
        icon="●",
        severity_strip="▐",
    )
    return _render_event_card(header)
