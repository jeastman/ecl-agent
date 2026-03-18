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
                with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        self.assertEqual(
                            cli.main(["--config", "ignored.toml", "run", "Inspect repo"]), 0
                        )
                        output = stdout.getvalue()
                self.assertIn("Task Accepted", output)
                self.assertIn("task_123", output)
                self.assertIn("agent logs task_123", output)

                with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        self.assertEqual(
                            cli.main(
                                [
                                    "--config",
                                    "ignored.toml",
                                    "status",
                                    "task_123",
                                    "--run-id",
                                    "run_456",
                                ]
                            ),
                            0,
                        )
                        output = stdout.getvalue()
                self.assertIn("Task Status", output)
                self.assertIn("completed", output)
                self.assertIn("Summary created.", output)

                with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        self.assertEqual(
                            cli.main(
                                [
                                    "--config",
                                    "ignored.toml",
                                    "logs",
                                    "task_123",
                                    "--run-id",
                                    "run_456",
                                ]
                            ),
                            0,
                        )
                        output = stdout.getvalue()
                self.assertIn("Event Stream", output)
                self.assertIn("task.created", output)
                self.assertIn("objective=Inspect repo", output)
                self.assertIn("researcher started: Inspect repo", output)
                self.assertIn("researcher status=success duration=0.42", output)
                self.assertIn("artifacts/repo_summary.md", output)

                with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        self.assertEqual(
                            cli.main(
                                [
                                    "--config",
                                    "ignored.toml",
                                    "artifacts",
                                    "task_123",
                                    "--run-id",
                                    "run_456",
                                ]
                            ),
                            0,
                        )
                        output = stdout.getvalue()
                self.assertIn("Artifacts", output)
                self.assertIn("artifact_1", output)
                self.assertIn("text/markdown", output)

                with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        self.assertEqual(
                            cli.main(["--config", "ignored.toml", "approvals", "task_123"]), 0
                        )
                        output = stdout.getvalue()
                self.assertIn("Approvals", output)
                self.assertIn("approval_1", output)

                with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        self.assertEqual(
                            cli.main(["--config", "ignored.toml", "diagnostics", "task_123"]), 0
                        )
                        output = stdout.getvalue()
                self.assertIn("Diagnostics", output)
                self.assertIn("diag_1", output)

                with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        self.assertEqual(
                            cli.main(
                                [
                                    "--config",
                                    "ignored.toml",
                                    "approve",
                                    "approval_1",
                                    "--decision",
                                    "approve",
                                ]
                            ),
                            0,
                        )
                        output = stdout.getvalue()
                self.assertIn("Approval Submitted", output)
                self.assertIn("True", output)
                self.assertIn("completed", output)

                with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        self.assertEqual(
                            cli.main(
                                [
                                    "--config",
                                    "ignored.toml",
                                    "resume",
                                    "task_123",
                                    "--run-id",
                                    "run_456",
                                ]
                            ),
                            0,
                        )
                        output = stdout.getvalue()
                self.assertIn("Task Resumed", output)
                self.assertIn("task_123", output)
                self.assertIn("completed", output)
                self.assertIn("Run resumed and completed.", output)

                with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        self.assertEqual(
                            cli.main(
                                [
                                    "--config",
                                    "ignored.toml",
                                    "memory",
                                    "--scope",
                                    "project",
                                ]
                            ),
                            0,
                        )
                        output = stdout.getvalue()
                self.assertIn("Memory Entries", output)
                self.assertIn("mem_1", output)

                with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        self.assertEqual(cli.main(["--config", "ignored.toml", "config"]), 0)
                        output = stdout.getvalue()
                self.assertIn("Runtime Config", output)
                self.assertIn('"api_token": "***REDACTED***"', output)


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
                            "event_type": "subagent.started",
                            "payload": {
                                "runId": "run_456",
                                "subagentId": "researcher",
                                "taskDescription": "Inspect repo",
                                "timestamp": "2026-03-11T10:00:00Z",
                            },
                        },
                    }
                )
            )
            print(
                json.dumps(
                    {
                        "type": "runtime.event",
                        "event": {
                            "event_type": "subagent.completed",
                            "payload": {
                                "runId": "run_456",
                                "subagentId": "researcher",
                                "status": "success",
                                "duration": 0.42,
                                "timestamp": "2026-03-11T10:00:01Z",
                            },
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
                                "artifact": {"logical_path": "/workspace/artifacts/repo_summary.md"}
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
                            "logical_path": "/workspace/artifacts/repo_summary.md",
                            "content_type": "text/markdown",
                            "persistence_class": "run",
                            "display_name": "repo_summary.md",
                        }
                    ]
                },
            }
            print(json.dumps(response))
        elif method == "task.approvals.list":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "correlation_id": correlation_id,
                "result": {
                    "approvals": [
                        {
                            "approval_id": "approval_1",
                            "status": "pending",
                            "type": "boundary",
                            "scope_summary": "file.write:/**",
                            "description": "Allow writes",
                            "created_at": "2026-03-10T00:00:00Z",
                        }
                    ]
                },
            }
            print(json.dumps(response))
        elif method == "task.diagnostics.list":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "correlation_id": correlation_id,
                "result": {
                    "diagnostics": [
                        {
                            "diagnostic_id": "diag_1",
                            "task_id": "task_123",
                            "run_id": "run_456",
                            "kind": "tool_rejected",
                            "message": "Network access denied",
                            "created_at": "2026-03-10T00:00:00Z",
                            "details": {"phase": "execute"},
                        }
                    ]
                },
            }
            print(json.dumps(response))
        elif method == "task.approve":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "correlation_id": correlation_id,
                "result": {
                    "approval_id": request["params"]["approval"]["approval_id"],
                    "accepted": True,
                    "status": "approved",
                    "task": {
                        "task_id": "task_123",
                        "run_id": "run_456",
                        "status": "completed",
                        "objective": "Inspect repo",
                    },
                },
            }
            print(json.dumps(response))
        elif method == "task.resume":
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
                        "latest_summary": "Run resumed and completed.",
                        "artifact_count": 1,
                    }
                },
            }
            print(json.dumps(response))
        elif method == "memory.inspect":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "correlation_id": correlation_id,
                "result": {
                    "scope": "project",
                    "count": 1,
                    "entries": [
                        {
                            "memory_id": "mem_1",
                            "scope": "project",
                            "namespace": "project.conventions",
                            "summary": "Convention",
                            "created_at": "2026-03-10T00:00:00Z",
                            "updated_at": "2026-03-10T00:00:00Z",
                            "provenance": {"task_id": "task_123"},
                        }
                    ],
                },
            }
            print(json.dumps(response))
        elif method == "config.get":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "correlation_id": correlation_id,
                "result": {
                    "loaded_profiles": [],
                    "config_sources": ["ignored.toml"],
                    "redactions": [{"path": "policy.api_token", "reason": "sensitive-key"}],
                    "effective_config": {"policy": {"api_token": "***REDACTED***"}},
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
