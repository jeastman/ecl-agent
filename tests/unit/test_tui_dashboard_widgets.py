from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.screens.dashboard import _artifact_card
from apps.tui.local_agent_tui.store.selectors import (
    ApprovalQueueItemViewModel,
    ArtifactItemViewModel,
)
from apps.tui.local_agent_tui.widgets.approval_queue import _approval_card


class DashboardWidgetRenderTests(unittest.TestCase):
    def test_approval_card_uses_card_layout_without_ascii_table_headers(self) -> None:
        rendered = _approval_card(
            ApprovalQueueItemViewModel(
                approval_id="approval_1",
                task_id="task_1234567890abcdef",
                run_id="run_1234567890abcdef",
                status="pending",
                request_type="boundary",
                policy_context="filesystem.write",
                requested_action="Approve filesystem write",
                description="tool permission",
                scope_summary="filesystem.write",
                created_at="2026-03-12T00:00:01Z",
                created_at_relative="2m ago",
                is_selected=True,
                is_highlighted=False,
            ),
            inbox_mode=False,
        )

        plain = rendered.plain
        self.assertIn("boundary approval", plain)
        self.assertIn("tool permission", plain)
        self.assertIn("filesystem.write", plain)
        self.assertIn("⚠", plain)
        self.assertIn("2m ago", plain)
        self.assertNotIn("Task        Type", plain)

    def test_approval_card_inbox_mode_includes_requested_action(self) -> None:
        rendered = _approval_card(
            ApprovalQueueItemViewModel(
                approval_id="approval_1",
                task_id="task_1",
                run_id="run_1",
                status="pending",
                request_type="boundary",
                policy_context="filesystem.write",
                requested_action="Approve filesystem write",
                description="tool permission",
                scope_summary="filesystem.write",
                created_at="2026-03-12T00:00:01Z",
                created_at_relative="2m ago",
                is_selected=False,
                is_highlighted=True,
            ),
            inbox_mode=True,
        )

        self.assertIn("Action: Approve filesystem write", rendered.plain)

    def test_artifact_card_renders_name_type_and_relative_time(self) -> None:
        rendered = _artifact_card(
            ArtifactItemViewModel(
                artifact_id="artifact_1",
                task_id="task_1234567890abcdef",
                run_id="run_1",
                logical_path="/workspace/artifacts/report.md",
                display_name="report.md",
                content_type="text/markdown",
                created_at="2026-03-12T00:00:02Z",
                created_at_relative="1m ago",
            )
        )

        plain = rendered.plain
        self.assertIn("report.md", plain)
        self.assertIn("markdown", plain)
        self.assertIn("1m ago", plain)
        self.assertIn("📝", plain)
