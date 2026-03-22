from __future__ import annotations

import io
import unittest

from rich.console import Console

from apps.tui.local_agent_tui.screens.help import _help_renderable
from apps.tui.local_agent_tui.store.app_state import AppState


class HelpScreenRenderableTests(unittest.TestCase):
    def test_help_renderable_groups_shortcuts_by_screen_context(self) -> None:
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=120)
        console.print(_help_renderable(AppState(active_screen="task_detail", focused_pane="timeline")))
        rendered = output.getvalue()

        self.assertIn("Current Screen", rendered)
        self.assertIn("Screen Shortcuts", rendered)
        self.assertIn("Dashboard", rendered)
        self.assertIn("Task Detail", rendered)
        self.assertIn("Approvals", rendered)
        self.assertIn("Artifacts", rendered)
        self.assertIn("Memory", rendered)
        self.assertIn("Config", rendered)
        self.assertIn("Diagnostics", rendered)
        self.assertIn("cancel [reason], reply <message>", rendered)
