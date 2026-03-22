from __future__ import annotations

import unittest

from rich.console import Console

from apps.tui.local_agent_tui.screens.dashboard import _artifact_card
from apps.tui.local_agent_tui.screens.dashboard import _phase_timeline_renderable
from apps.tui.local_agent_tui.screens.dashboard import _task_summary_text
from apps.tui.local_agent_tui.store.selectors import (
    ApprovalQueueItemViewModel,
    ArtifactItemViewModel,
    TaskListItemViewModel,
    TaskSummaryViewModel,
)
from apps.tui.local_agent_tui.widgets.approval_queue import _approval_card
from apps.tui.local_agent_tui.widgets.task_list import _row_content


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

    def test_task_summary_renders_progress_elapsed_and_phase_timeline(self) -> None:
        rendered = _task_summary_text(
            TaskSummaryViewModel(
                task_id="task_1",
                run_id="run_1",
                status="executing",
                objective="Inspect repo",
                latest_summary="Writing summary",
                created_at="2026-03-12T00:00:00Z",
                updated_at="2026-03-12T00:15:00Z",
                awaiting_approval=False,
                artifact_count=2,
                actionable_label="Continue",
                actionable_hint="Task is running.",
                current_phase="executing",
                todo_completed_count=2,
                todo_total_count=4,
                progress_percent=50,
                elapsed_label="15m 0s",
                phase_steps=("accepted", "planning", "executing", "completed"),
                current_phase_index=2,
            )
        )

        console = Console(width=120, record=True)
        console.print(rendered)
        plain = console.export_text()
        self.assertIn("Progress", plain)
        self.assertIn("50%", plain)
        self.assertIn("Elapsed", plain)
        self.assertIn("15m 0s", plain)
        self.assertIn("Planning", plain)
        self.assertIn("Executing", plain)

    def test_phase_timeline_centers_markers_under_phase_columns(self) -> None:
        summary = TaskSummaryViewModel(
            task_id="task_1",
            run_id="run_1",
            status="executing",
            objective="Inspect repo",
            latest_summary="Writing summary",
            created_at="2026-03-12T00:00:00Z",
            updated_at="2026-03-12T00:15:00Z",
            awaiting_approval=False,
            artifact_count=2,
            actionable_label="Continue",
            actionable_hint="Task is running.",
            current_phase="executing",
            todo_completed_count=2,
            todo_total_count=4,
            progress_percent=50,
            elapsed_label="15m 0s",
            phase_steps=("accepted", "planning", "executing", "completed"),
            current_phase_index=2,
        )

        phase = _phase_timeline_renderable(summary)

        self.assertIsNotNone(phase)
        lines = phase.plain.splitlines()
        segment_width = max(len(step) for step in summary.phase_steps) + 2
        expected = (
            "✓".center(segment_width)
            + "  "
            + "✓".center(segment_width)
            + "  "
            + "●".center(segment_width)
            + "  "
            + "○".center(segment_width)
        )
        self.assertEqual(lines[2], expected)

    def test_compact_task_row_truncates_objective_to_preserve_time_line(self) -> None:
        rendered = _row_content(
            TaskListItemViewModel(
                task_id="task_1",
                run_id="run_1",
                status="completed",
                objective="There is an investor meeting coming up. Prepare a briefing document based on the data in the workspace.",
                updated_at="2026-03-12T00:00:02Z",
                awaiting_approval=False,
                artifact_count=2,
                is_selected=True,
                is_highlighted=False,
            ),
            compact=True,
            width=24,
        )

        lines = rendered.plain.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("Mar 12", lines[1])
        self.assertIn("2", lines[1])
