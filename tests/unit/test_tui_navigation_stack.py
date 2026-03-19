from __future__ import annotations

import unittest
from dataclasses import replace

from apps.tui.local_agent_tui.store.app_state import AppState, AppStateStore, UiMessage
from apps.tui.local_agent_tui.store.reducers import reduce_app_state


class TestNavigationStackDefaults(unittest.TestCase):
    def test_navigation_stack_default_is_dashboard(self) -> None:
        state = AppState()
        self.assertEqual(state.navigation_stack, ["dashboard"])

    def test_last_focused_pane_by_screen_default_is_empty(self) -> None:
        state = AppState()
        self.assertEqual(state.last_focused_pane_by_screen, {})

    def test_navigation_stack_fields_exist_in_ui_message(self) -> None:
        msg: UiMessage = {
            "kind": "ui",
            "navigation_stack": ["dashboard", "approvals"],
            "last_focused_pane_by_screen": {"dashboard": "tasks"},
        }
        self.assertEqual(msg["navigation_stack"], ["dashboard", "approvals"])


class TestNavigationStackReducer(unittest.TestCase):
    def test_reducer_updates_navigation_stack_when_present(self) -> None:
        state = AppState()
        msg: UiMessage = {"kind": "ui", "navigation_stack": ["dashboard", "approvals"]}
        new_state = reduce_app_state(state, msg)
        self.assertEqual(new_state.navigation_stack, ["dashboard", "approvals"])

    def test_reducer_preserves_navigation_stack_when_absent(self) -> None:
        state = AppState()
        msg: UiMessage = {"kind": "ui", "active_screen": "approvals"}
        new_state = reduce_app_state(state, msg)
        self.assertEqual(new_state.navigation_stack, ["dashboard"])

    def test_reducer_updates_last_focused_pane_by_screen_when_present(self) -> None:
        state = AppState()
        msg: UiMessage = {
            "kind": "ui",
            "last_focused_pane_by_screen": {"dashboard": "summary"},
        }
        new_state = reduce_app_state(state, msg)
        self.assertEqual(new_state.last_focused_pane_by_screen, {"dashboard": "summary"})

    def test_reducer_merges_focused_pane_into_last_focused_when_focused_pane_changes(self) -> None:
        state = AppState()
        msg: UiMessage = {"kind": "ui", "focused_pane": "summary"}
        new_state = reduce_app_state(state, msg)
        self.assertEqual(new_state.last_focused_pane_by_screen.get("dashboard"), "summary")

    def test_reducer_preserves_last_focused_when_neither_key_present(self) -> None:
        state = replace(AppState(), last_focused_pane_by_screen={"dashboard": "tasks"})
        msg: UiMessage = {"kind": "ui", "active_screen": "approvals"}
        new_state = reduce_app_state(state, msg)
        self.assertEqual(new_state.last_focused_pane_by_screen, {"dashboard": "tasks"})

    def test_multiple_navigations_accumulate(self) -> None:
        state = AppState()
        state = reduce_app_state(state, {"kind": "ui", "navigation_stack": ["dashboard", "task_detail"]})
        state = reduce_app_state(state, {"kind": "ui", "navigation_stack": ["dashboard", "task_detail", "artifacts"]})
        self.assertEqual(state.navigation_stack, ["dashboard", "task_detail", "artifacts"])


if __name__ == "__main__":
    unittest.main()
