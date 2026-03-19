from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.renderables import badge, block, join, metadata_line


class RenderablesTests(unittest.TestCase):
    def test_join_preserves_bracket_heavy_text(self) -> None:
        rendered = join(["call[search]", '["curl","-s","-H"]'], separator="  ")
        self.assertEqual(rendered.plain, 'call[search]  ["curl","-s","-H"]')

    def test_metadata_line_preserves_validation_payload(self) -> None:
        rendered = metadata_line(
            [
                ("Scope", '[type=list_type, input_value=\'["find","/"]\', input_type=str]'),
                ("Status", "failed"),
            ]
        )
        self.assertIn('[type=list_type, input_value=\'["find","/"]\', input_type=str]', rendered.plain)

    def test_block_keeps_plain_text_for_nested_payloads(self) -> None:
        rendered = block(
            [
                "Summary",
                '[type=list_type, input_value=\'["python3","-c","import os"]\', input_type=str]',
            ]
        )
        combined = "\n".join(segment.plain for segment in rendered.renderables)
        self.assertIn('["python3","-c","import os"]', combined)

    def test_badge_plain_text_is_operator_readable(self) -> None:
        rendered = badge("FAILED", style="red")
        self.assertEqual(rendered.plain, "FAILED")
