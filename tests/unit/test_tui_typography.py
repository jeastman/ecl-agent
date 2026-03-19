from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.theme.typography import (
    title,
    label,
    value,
    muted,
    status_badge,
    key_hint,
    TEXT_PRIMARY,
    STATUS_COLORS,
)
from apps.tui.local_agent_tui.theme.empty_states import render_empty_state
from apps.tui.local_agent_tui.theme.colors import (
    TEXT_TITLE,
    TEXT_SECONDARY,
    TEXT_MUTED_DEEP,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    STATUS_WARNING,
    STATUS_DANGER,
    STATUS_INFO,
)


class TestTitle(unittest.TestCase):
    def test_plain_text_matches_input(self) -> None:
        result = title("Hello")
        self.assertEqual(result.plain, "Hello")

    def test_style_contains_bold(self) -> None:
        result = title("Hello")
        self.assertIn("bold", str(result.style))

    def test_style_contains_text_title_color(self) -> None:
        result = title("Hello")
        style_str = str(result.style)
        self.assertIn(TEXT_TITLE, style_str)


class TestLabel(unittest.TestCase):
    def test_plain_text_matches_input(self) -> None:
        result = label("My Label")
        self.assertEqual(result.plain, "My Label")

    def test_style_is_text_secondary(self) -> None:
        result = label("My Label")
        self.assertIn(TEXT_SECONDARY, str(result.style))


class TestValue(unittest.TestCase):
    def test_plain_text_matches_input(self) -> None:
        result = value("some value")
        self.assertEqual(result.plain, "some value")

    def test_style_is_text_primary(self) -> None:
        result = value("some value")
        self.assertIn(TEXT_PRIMARY, str(result.style))

    def test_text_primary_constant_is_correct(self) -> None:
        self.assertEqual(TEXT_PRIMARY, "#e8edf2")


class TestMuted(unittest.TestCase):
    def test_plain_text_matches_input(self) -> None:
        result = muted("quiet text")
        self.assertEqual(result.plain, "quiet text")

    def test_style_is_text_muted_deep(self) -> None:
        result = muted("quiet text")
        self.assertIn(TEXT_MUTED_DEEP, str(result.style))


class TestStatusBadge(unittest.TestCase):
    def _get_style_str(self, text_obj) -> str:
        # For a simple Text object, style is set on the Text itself
        return str(text_obj.style)

    def test_executing_uses_status_running(self) -> None:
        result = status_badge("executing")
        self.assertIn(STATUS_RUNNING, self._get_style_str(result))
        self.assertIn("bold", self._get_style_str(result))

    def test_planning_uses_status_running(self) -> None:
        result = status_badge("planning")
        self.assertIn(STATUS_RUNNING, self._get_style_str(result))

    def test_running_uses_status_running(self) -> None:
        result = status_badge("running")
        self.assertIn(STATUS_RUNNING, self._get_style_str(result))

    def test_completed_uses_status_success(self) -> None:
        result = status_badge("completed")
        self.assertIn(STATUS_SUCCESS, self._get_style_str(result))

    def test_failed_uses_status_danger(self) -> None:
        result = status_badge("failed")
        self.assertIn(STATUS_DANGER, self._get_style_str(result))

    def test_paused_uses_status_warning(self) -> None:
        result = status_badge("paused")
        self.assertIn(STATUS_WARNING, self._get_style_str(result))

    def test_awaiting_approval_uses_status_warning(self) -> None:
        result = status_badge("awaiting_approval")
        self.assertIn(STATUS_WARNING, self._get_style_str(result))

    def test_accepted_uses_status_running(self) -> None:
        result = status_badge("accepted")
        self.assertIn(STATUS_RUNNING, self._get_style_str(result))

    def test_unknown_status_falls_back_to_status_info(self) -> None:
        result = status_badge("unknown_xyz")
        self.assertIn(STATUS_INFO, self._get_style_str(result))

    def test_badge_text_format_with_padding(self) -> None:
        result = status_badge("running")
        self.assertEqual(result.plain, " RUNNING ")

    def test_badge_text_is_uppercased(self) -> None:
        result = status_badge("completed")
        self.assertEqual(result.plain, " COMPLETED ")

    def test_case_insensitive_lookup(self) -> None:
        result = status_badge("RUNNING")
        self.assertIn(STATUS_RUNNING, self._get_style_str(result))


class TestKeyHint(unittest.TestCase):
    def test_plain_contains_key_and_action(self) -> None:
        result = key_hint("n", "new task")
        self.assertIn("n", result.plain)
        self.assertIn("new task", result.plain)

    def test_first_span_uses_bold_reverse(self) -> None:
        result = key_hint("n", "new task")
        self.assertTrue(len(result._spans) >= 1)
        first_style = str(result._spans[0].style)
        self.assertIn("bold", first_style)
        self.assertIn("reverse", first_style)

    def test_second_span_uses_text_secondary(self) -> None:
        result = key_hint("n", "new task")
        self.assertTrue(len(result._spans) >= 2)
        second_style = str(result._spans[1].style)
        self.assertIn(TEXT_SECONDARY, second_style)

    def test_key_wrapped_in_spaces(self) -> None:
        result = key_hint("q", "quit")
        self.assertIn(" q ", result.plain)

    def test_action_prefixed_with_space(self) -> None:
        result = key_hint("q", "quit")
        self.assertIn(" quit", result.plain)


class TestRenderEmptyState(unittest.TestCase):
    def test_known_key_tasks_contains_icon(self) -> None:
        result = render_empty_state("tasks")
        self.assertIn("◇", result.plain)

    def test_known_key_tasks_contains_heading(self) -> None:
        result = render_empty_state("tasks")
        self.assertIn("No tasks yet", result.plain)

    def test_known_key_tasks_contains_hint(self) -> None:
        result = render_empty_state("tasks")
        self.assertIn("Press n to create your first task", result.plain)

    def test_known_key_approvals_uses_checkmark_icon(self) -> None:
        result = render_empty_state("approvals")
        self.assertIn("✓", result.plain)

    def test_unknown_key_returns_nothing_here(self) -> None:
        result = render_empty_state("nonexistent_key")
        self.assertIn("Nothing here", result.plain)

    def test_unknown_key_returns_text_with_icon(self) -> None:
        result = render_empty_state("nonexistent_key")
        self.assertIn("◇", result.plain)

    def test_all_known_keys_render_without_error(self) -> None:
        known_keys = [
            "tasks", "events", "approvals", "artifacts", "subagents",
            "plan", "notifications", "memory", "diagnostics", "config",
        ]
        for key in known_keys:
            result = render_empty_state(key)
            self.assertIsNotNone(result.plain, f"render_empty_state({key!r}) returned None plain")


if __name__ == "__main__":
    unittest.main()
