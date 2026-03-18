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

        self.assertIn(r"call\[search]", rendered)
        self.assertIn(r"task-runner\[worker]", rendered)
        self.assertIn(r"FAILED\[hard]", rendered)
        self.assertIn(r"\[type=less_than_equal, input_value=100, input_type=int]", rendered)
