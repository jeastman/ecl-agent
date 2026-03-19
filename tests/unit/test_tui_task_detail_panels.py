from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.widgets.task_detail_panels import (
    _render_notification_line,
)


class TaskDetailPanelsTests(unittest.TestCase):
    def test_notification_line_shape_can_include_bracketed_error_text(self) -> None:
        rendered = _render_notification_line(
            timestamp="2026-03-18T16:27:39Z",
            severity="error",
            summary=(
                "1 validation error for call[search]\n"
                "limit\n"
                "  Input should be less than or equal to 20 "
                "[type=less_than_equal, input_value=100, input_type=int]"
            ),
        )
        combined = "\n".join(segment.plain for segment in rendered.renderables)
        self.assertIn("call[search]", combined)
        self.assertIn("[type=less_than_equal, input_value=100, input_type=int]", combined)
