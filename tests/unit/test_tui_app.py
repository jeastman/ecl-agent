from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.app import _TEXTUAL_IMPORT_ERROR


@unittest.skipIf(_TEXTUAL_IMPORT_ERROR is not None, "textual is not installed")
class TuiAppSmokeTests(unittest.TestCase):
    def test_textual_imports_are_available_for_app_boot(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI

        app = AgentTUI(
            config_path="docs/architecture/runtime.example.toml",
            task_id=None,
            run_id=None,
        )
        self.assertIsNotNone(app)
