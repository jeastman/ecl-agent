from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.cli.local_agent_cli import cli


class CliTests(unittest.TestCase):
    def test_handle_submit_defaults_workspace_root_to_cwd(self) -> None:
        captured: dict[str, object] = {}

        def fake_send_rpc(command: list[str], request: object) -> dict[str, object]:
            del command
            captured["request"] = request
            return {
                "correlation_id": "corr_1",
                "result": {
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "status": "accepted",
                    "accepted_at": "2026-03-10T00:00:00Z",
                },
            }

        with patch.object(cli, "send_rpc", side_effect=fake_send_rpc):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_submit(
                    config_path="docs/architecture/runtime.example.toml",
                    objective="Inspect the repo",
                    workspace_roots=[],
                    constraints=[],
                    success_criteria=[],
                )
        self.assertEqual(exit_code, 0)
        request = captured["request"]
        self.assertEqual(
            request.params["task"]["workspace_roots"],  # type: ignore[attr-defined]
            [str(Path.cwd())],
        )
        self.assertIn("correlation_id=corr_1", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
