from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.screens.diagnostics import (
    _render_diagnostic_detail,
    _render_diagnostic_list_item,
)


class _DiagnosticItem:
    def __init__(self, *, is_selected: bool, kind: str, created_at: str, message: str) -> None:
        self.is_selected = is_selected
        self.kind = kind
        self.created_at = created_at
        self.message = message


class DiagnosticsScreenTests(unittest.TestCase):
    def test_render_diagnostic_list_item_keeps_bracketed_payload_plain(self) -> None:
        item = _DiagnosticItem(
            is_selected=True,
            kind="validation_error",
            created_at="2026-03-18T17:20:00Z",
            message=(
                "Input should be a valid list "
                "[type=list_type, input_value='[\"curl\",\"-s\",\"-H\","
                "\"Authorization: Bearer ... alternative approach\"]', input_type=str]"
            ),
        )
        rendered = _render_diagnostic_list_item(item)
        plain = rendered.plain
        self.assertIn("validation_error", plain)
        self.assertIn("[type=list_type, input_value='[\"curl\",\"-s\",\"-H\",", plain)
        self.assertIn("input_type=str]", plain)

    def test_render_diagnostic_detail_keeps_bracketed_payload_plain(self) -> None:
        rendered = _render_diagnostic_detail(
            "Validation",
            "Diagnostic summary",
            (
                "Tool call failed with payload "
                "[type=list_type, input_value='[\"curl\",\"-s\"]', input_type=str]"
            ),
            "",
            "Retry with a valid payload.",
        )
        combined = "\n".join(segment.plain for segment in rendered.renderables)
        self.assertIn("Diagnostic summary", combined)
        self.assertIn("[type=list_type, input_value='[\"curl\",\"-s\"]', input_type=str]", combined)
