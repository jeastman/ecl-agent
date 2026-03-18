from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.widgets.log_view import _render_log_line


class _Line:
    def __init__(
        self,
        *,
        timestamp: str,
        level: str,
        source_name: str | None,
        message: str,
        is_highlighted: bool,
    ) -> None:
        self.timestamp = timestamp
        self.level = level
        self.source_name = source_name
        self.message = message
        self.is_highlighted = is_highlighted


class LogViewWidgetTests(unittest.TestCase):
    def test_render_log_line_keeps_bracket_heavy_payload_as_plain_text(self) -> None:
        line = _Line(
            timestamp="2026-03-18T17:12:30Z",
            level="ERROR",
            source_name="task-runner",
            message=(
                "1 validation error for call[execute_command]\n"
                "arguments\n"
                "  Input should be a valid list "
                "[type=list_type, input_value='[\"find\", \"/\", \"-name\", "
                "\"...2>/dev/null | head -20]', input_type=str]"
            ),
            is_highlighted=False,
        )

        rendered = _render_log_line(line)
        plain = rendered.plain
        self.assertIn("call[execute_command]", plain)
        self.assertIn("[type=list_type, input_value='[\"find\", \"/\", \"-name\", ", plain)
        self.assertIn("input_type=str]", plain)
