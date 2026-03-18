from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.widgets.task_detail_panels import (
    _render_notification_line,
    _severity_markup,
)


class TaskDetailPanelsTests(unittest.TestCase):
    def test_severity_markup_escapes_dynamic_label_text(self) -> None:
        rendered = _severity_markup("attention[worker]")
        self.assertIn(r"\[ATTENTION[WORKER]\]", rendered)

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
        self.assertIn(r"call\[search]", rendered)
        self.assertIn(r"\[type=less_than_equal, input_value=100, input_type=int]", rendered)
