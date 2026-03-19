from __future__ import annotations

import unittest
from dataclasses import replace

from rich.text import Text

from apps.tui.local_agent_tui.store.app_state import AppState
from apps.tui.local_agent_tui.store.selectors import screen_breadcrumb
from apps.tui.local_agent_tui.theme.colors import TEXT_MUTED_DEEP, TEXT_PRIMARY, TEXT_SECONDARY


class TestScreenBreadcrumb(unittest.TestCase):
    def test_dashboard_only_returns_dashboard(self) -> None:
        state = AppState()  # navigation_stack defaults to ["dashboard"]
        result = screen_breadcrumb(state)
        self.assertEqual(result.plain.strip(), "Dashboard")

    def test_dashboard_and_approvals(self) -> None:
        state = replace(AppState(), navigation_stack=["dashboard", "approvals"])
        result = screen_breadcrumb(state)
        self.assertIn("Dashboard", result.plain)
        self.assertIn("Approvals", result.plain)
        self.assertIn("›", result.plain)

    def test_task_detail_shows_truncated_task_id(self) -> None:
        state = replace(
            AppState(),
            navigation_stack=["dashboard", "task_detail"],
            selected_task_id="tsk_abc123def456",
        )
        result = screen_breadcrumb(state)
        self.assertIn("Task", result.plain)
        self.assertIn("tsk_", result.plain)

    def test_task_detail_with_none_task_id_does_not_crash(self) -> None:
        state = replace(
            AppState(),
            navigation_stack=["dashboard", "task_detail"],
            selected_task_id=None,
        )
        result = screen_breadcrumb(state)
        self.assertIn("Task", result.plain)

    def test_unknown_screen_uses_screen_name_as_fallback(self) -> None:
        state = replace(AppState(), navigation_stack=["dashboard", "unknown_screen"])
        result = screen_breadcrumb(state)
        self.assertIn("unknown_screen", result.plain)

    def test_memory_screen(self) -> None:
        state = replace(AppState(), navigation_stack=["dashboard", "memory"])
        result = screen_breadcrumb(state)
        self.assertIn("Memory", result.plain)

    def test_diagnostics_screen(self) -> None:
        state = replace(AppState(), navigation_stack=["dashboard", "diagnostics"])
        result = screen_breadcrumb(state)
        self.assertIn("Diagnostics", result.plain)

    def test_artifacts_screen(self) -> None:
        state = replace(AppState(), navigation_stack=["dashboard", "artifacts"])
        result = screen_breadcrumb(state)
        self.assertIn("Artifacts", result.plain)

    def test_config_screen(self) -> None:
        state = replace(AppState(), navigation_stack=["dashboard", "config"])
        result = screen_breadcrumb(state)
        self.assertIn("Config", result.plain)

    def test_returns_rich_text(self) -> None:
        state = AppState()
        self.assertIsInstance(screen_breadcrumb(state), Text)


if __name__ == "__main__":
    unittest.main()
