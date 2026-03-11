from __future__ import annotations

import io
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.cli.local_agent_cli import cli
from apps.cli.local_agent_cli.client import RuntimeClient


class CliIntegrationTests(unittest.TestCase):
    def test_cli_run_status_logs_and_artifacts_via_runtime_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / "fake_runtime.py"
            script_path.write_text(_fake_runtime_script(), encoding="utf-8")

            def fake_make_client(config_path: str) -> RuntimeClient:
                del config_path
                return RuntimeClient(
                    "ignored.toml",
                    command_factory=lambda _: [sys.executable, str(script_path)],
                )

            with patch.object(cli, "make_client", side_effect=fake_make_client):
                with patch("sys.stdout", new=io.StringIO()) as stdout:
                    self.assertEqual(cli.main(["--config", "ignored.toml", "run", "Inspect repo"]), 0)
                    output = stdout.getvalue()
                self.assertIn("task_id=task_123", output)
                self.assertIn("hint=agent logs task_123", output)

                with patch("sys.stdout", new=io.StringIO()) as stdout:
                    self.assertEqual(
                        cli.main(["--config", "ignored.toml", "status", "task_123", "--run-id", "run_456"]),
                        0,
                    )
                    output = stdout.getvalue()
                self.assertIn("status=completed", output)
                self.assertIn("latest_summary=Summary created.", output)
                self.assertIn("active_subagent=primary", output)

                with patch("sys.stdout", new=io.StringIO()) as stdout:
                    self.assertEqual(
                        cli.main(["--config", "ignored.toml", "logs", "task_123", "--run-id", "run_456"]),
                        0,
                    )
                    output = stdout.getvalue()
                lines = output.strip().splitlines()
                self.assertIn("stream_open=True", lines[0])
                self.assertEqual(lines[1], "[task.created] objective=Inspect repo")
                self.assertEqual(lines[2], "[artifact.created] artifacts/repo_summary.md")

                with patch("sys.stdout", new=io.StringIO()) as stdout:
                    self.assertEqual(
                        cli.main(
                            ["--config", "ignored.toml", "artifacts", "task_123", "--run-id", "run_456"]
                        ),
                        0,
                    )
                    output = stdout.getvalue()
                self.assertIn("artifact_id=artifact_1", output)
                self.assertIn("content_type=text/markdown", output)


def _fake_runtime_script() -> str:
    return textwrap.dedent(
        """
        from __future__ import annotations

        import json
        import sys

        request = json.loads(sys.stdin.readline())
        method = request["method"]
        correlation_id = request.get("correlation_id")

        if method == "task.create":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "correlation_id": correlation_id,
                "result": {
                    "task_id": "task_123",
                    "run_id": "run_456",
                    "status": "accepted",
                    "accepted_at": "2026-03-10T00:00:00Z",
                },
            }
            print(json.dumps(response))
        elif method == "task.get":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "correlation_id": correlation_id,
                "result": {
                    "task": {
                        "task_id": "task_123",
                        "run_id": "run_456",
                        "status": "completed",
                        "objective": "Inspect repo",
                        "current_phase": "completed",
                        "latest_summary": "Summary created.",
                        "active_subagent": "primary",
                        "artifact_count": 1,
                    }
                },
            }
            print(json.dumps(response))
        elif method == "task.logs.stream":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "correlation_id": correlation_id,
                "result": {
                    "task_id": "task_123",
                    "run_id": "run_456",
                    "stream_open": True,
                },
            }
            print(json.dumps(response))
            print(
                json.dumps(
                    {
                        "type": "runtime.event",
                        "event": {
                            "event_type": "task.created",
                            "payload": {"objective": "Inspect repo"},
                        },
                    }
                )
            )
            print(
                json.dumps(
                    {
                        "type": "runtime.event",
                        "event": {
                            "event_type": "artifact.created",
                            "payload": {
                                "artifact": {"logical_path": "artifacts/repo_summary.md"}
                            },
                        },
                    }
                )
            )
        elif method == "task.artifacts.list":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "correlation_id": correlation_id,
                "result": {
                    "artifacts": [
                        {
                            "artifact_id": "artifact_1",
                            "logical_path": "artifacts/repo_summary.md",
                            "content_type": "text/markdown",
                            "persistence_class": "run",
                            "display_name": "repo_summary.md",
                        }
                    ]
                },
            }
            print(json.dumps(response))
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "correlation_id": correlation_id,
                "error": {"code": -32601, "message": f"unknown method: {method}"},
            }
            print(json.dumps(response))
        """
    )


if __name__ == "__main__":
    unittest.main()
