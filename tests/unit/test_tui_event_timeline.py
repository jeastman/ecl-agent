from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.theme.colors import SEVERITY_INFO
from apps.tui.local_agent_tui.store.selectors import TimelineEventViewModel
from apps.tui.local_agent_tui.widgets.event_timeline import (
    _aligned_timestamp_display,
    _render_event_card,
    _render_event_line,
    _severity_color,
)


class EventTimelineWidgetTests(unittest.TestCase):
    def test_render_event_line_escapes_rich_markup_in_dynamic_fields(self) -> None:
        rendered = _render_event_line(
            timestamp="2026-03-18T16:27:39Z",
            event_type="task.failed",
            severity="error",
            summary=(
                "1 validation error for call[search]\n"
                "limit\n"
                "  Input should be less than or equal to 20 "
                "[type=less_than_equal, input_value=100, input_type=int]"
            ),
            repeat_count=1,
            source_name="task-runner[worker]",
            highlight=True,
            highlight_label="FAILED[hard]",
        )

        plain = rendered.plain
        self.assertIn("call[search]", plain)
        self.assertIn("task-runner[worker]", plain)
        self.assertIn("FAILED[hard]", plain)
        self.assertIn("[type=less_than_equal,", plain)
        self.assertIn("input_value=100, input_type=int]", plain)

    def test_render_event_line_marks_collapsed_events_as_repeated(self) -> None:
        rendered = _render_event_line(
            timestamp="16:27:39",
            event_type="tool.called",
            severity="success",
            summary="npm install",
            repeat_count=3,
            source_name="executor",
            highlight=False,
            highlight_label=None,
        )

        self.assertIn("×3", rendered.plain)
        self.assertIn("npm install (repeated)", rendered.plain)
        self.assertIn("▐", rendered.plain)

    def test_info_severity_uses_dedicated_info_color(self) -> None:
        self.assertEqual(_severity_color("info"), SEVERITY_INFO)

    def test_grouped_minute_timestamps_keep_header_columns_aligned(self) -> None:
        full = _render_event_card(
            TimelineEventViewModel(
                timestamp="2026-03-18T16:27:39Z",
                timestamp_display="11:43:12",
                event_type="tool.called",
                severity_label="INFO",
                summary="read_file /workspace/foo.md",
                severity="info",
                detail_lines=[],
                collapsed_detail_lines=[],
                detail_overflow_count=0,
                repeat_count=1,
                source_label="read_file",
                show_priority_highlight=False,
                priority_label=None,
                icon="🔧",
                severity_strip="▐",
            ),
            width=80,
        )
        grouped = _render_event_card(
            TimelineEventViewModel(
                timestamp="2026-03-18T16:27:39Z",
                timestamp_display=":28",
                event_type="tool.called",
                severity_label="INFO",
                summary="read_file /workspace/bar.md",
                severity="info",
                detail_lines=[],
                collapsed_detail_lines=[],
                detail_overflow_count=0,
                repeat_count=1,
                source_label="read_file",
                show_priority_highlight=False,
                priority_label=None,
                icon="🔧",
                severity_strip="▐",
            ),
            width=80,
        )

        full_line = full.plain.splitlines()[0]
        grouped_line = grouped.plain.splitlines()[0]
        self.assertEqual(full_line.index("INFO"), grouped_line.index("INFO"))
        self.assertEqual(_aligned_timestamp_display(":28"), "     :28")
        self.assertEqual(_aligned_timestamp_display(":16", has_marker=True), ":16")

    def test_event_card_keeps_severity_strip_aligned_on_child_lines(self) -> None:
        rendered = _render_event_card(
            TimelineEventViewModel(
                timestamp="2026-03-18T16:27:39Z",
                timestamp_display="16:27:39",
                event_type="tool.rejected",
                severity_label="ATTN",
                summary="command rejected",
                severity="attention",
                detail_lines=["Tool: execute_command", "Reason: bad args"],
                collapsed_detail_lines=["Tool: execute_command", "Reason: bad args"],
                detail_overflow_count=0,
                repeat_count=1,
                source_label="executor",
                show_priority_highlight=False,
                priority_label=None,
                icon="🔧",
                severity_strip="▐",
            ),
            width=80,
        )

        lines = rendered.plain.splitlines()
        self.assertTrue(lines[0].startswith("▐ "))
        self.assertTrue(lines[1].startswith("▐"))
        self.assertTrue(lines[2].startswith("▐"))

    def test_event_card_wraps_long_lines_with_strip_and_parent_indent(self) -> None:
        rendered = _render_event_card(
            TimelineEventViewModel(
                timestamp="2026-03-18T16:27:39Z",
                timestamp_display="16:27:39",
                event_type="tool.rejected",
                severity_label="ATTN",
                summary="execute_command rejected because the command contains shell control syntax and needs a real argv list",
                severity="attention",
                detail_lines=[
                    "Tool: execute_command",
                    "Reason: command contains shell control syntax and must be invoked as a real argv list",
                ],
                collapsed_detail_lines=[
                    "Tool: execute_command",
                    "Reason: command contains shell control syntax and must be invoked as a real argv list",
                ],
                detail_overflow_count=0,
                repeat_count=1,
                source_label="execute_command",
                show_priority_highlight=False,
                priority_label=None,
                icon="🔧",
                severity_strip="▐",
            ),
            width=44,
        )

        lines = rendered.plain.splitlines()
        self.assertGreater(len(lines), 4)
        self.assertTrue(any(line.startswith("▐       execute_command") for line in lines))
        self.assertTrue(any(line.startswith("▐       └─ Reason:") for line in lines))
        self.assertTrue(any(line.startswith("▐          ") for line in lines))
