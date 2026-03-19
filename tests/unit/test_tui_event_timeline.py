from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.widgets.event_timeline import _render_event_line


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
        self.assertIn("[type=less_than_equal, input_value=100, input_type=int]", plain)

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
