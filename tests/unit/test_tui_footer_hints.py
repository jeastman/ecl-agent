from __future__ import annotations

import unittest
from dataclasses import replace

from rich.text import Text

from apps.tui.local_agent_tui.store.app_state import AppState
from apps.tui.local_agent_tui.store.selectors import footer_hints


def _state_for_screen(screen: str, **kwargs: object) -> AppState:
    return replace(AppState(), active_screen=screen, **kwargs)  # type: ignore[arg-type]


class TestFooterHintsReturnType(unittest.TestCase):
    def test_returns_rich_text(self) -> None:
        self.assertIsInstance(footer_hints(AppState()), Text)

    def test_non_empty_for_dashboard(self) -> None:
        result = footer_hints(AppState())
        self.assertTrue(len(result.plain) > 0)


class TestFooterHintsDashboard(unittest.TestCase):
    def test_contains_palette_hint(self) -> None:
        result = footer_hints(AppState())
        self.assertIn("G", result.plain)
        self.assertIn("Palette", result.plain)

    def test_contains_new_task_hint(self) -> None:
        result = footer_hints(AppState())
        self.assertIn("N", result.plain)
        self.assertIn("New Task", result.plain)


class TestFooterHintsTaskDetail(unittest.TestCase):
    def test_contains_esc_dashboard(self) -> None:
        state = _state_for_screen("task_detail")
        result = footer_hints(state)
        self.assertIn("Esc", result.plain)
        self.assertIn("Dashboard", result.plain)


class TestFooterHintsApprovals(unittest.TestCase):
    def test_contains_approve_hint(self) -> None:
        state = _state_for_screen("approvals")
        result = footer_hints(state)
        self.assertIn("A", result.plain)
        self.assertIn("Approve", result.plain)


class TestFooterHintsConfig(unittest.TestCase):
    def test_contains_refresh_hint(self) -> None:
        state = _state_for_screen("config")
        result = footer_hints(state)
        self.assertIn("Refresh", result.plain)


class TestFooterHintsArtifacts(unittest.TestCase):
    def test_contains_move_hint(self) -> None:
        state = _state_for_screen("artifacts")
        result = footer_hints(state)
        self.assertIn("Move", result.plain)


class TestFooterHintsMemory(unittest.TestCase):
    def test_contains_refresh_hint(self) -> None:
        state = _state_for_screen("memory")
        result = footer_hints(state)
        self.assertIn("Refresh", result.plain)


class TestFooterHintsDiagnostics(unittest.TestCase):
    def test_contains_back_hint(self) -> None:
        state = _state_for_screen("diagnostics")
        result = footer_hints(state)
        self.assertIn("Back", result.plain)


if __name__ == "__main__":
    unittest.main()
