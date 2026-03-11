from __future__ import annotations

import io
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from apps.cli.local_agent_cli import cli
from apps.cli.local_agent_cli.client import StreamResponse


class _FakeClient:
    def __init__(self) -> None:
        self.requests: list[object] = []
        self.response = {
            "correlation_id": "corr_1",
            "result": {
                "task_id": "task_1",
                "run_id": "run_1",
                "status": "accepted",
                "accepted_at": "2026-03-10T00:00:00Z",
            },
        }
        self.stream_response = StreamResponse(
            response={
                "result": {
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "stream_open": True,
                }
            },
            events=[],
        )

    def send(self, request: object) -> dict[str, object]:
        self.requests.append(request)
        return cast(dict[str, object], self.response)

    def stream(self, request: object) -> StreamResponse:
        self.requests.append(request)
        return self.stream_response

    def consume_stream(self, request: object, on_response=None, on_event=None) -> dict[str, object]:
        self.requests.append(request)
        if on_response is not None:
            on_response(self.stream_response.response)
        if on_event is not None:
            for event in self.stream_response.events:
                on_event(event)
        return cast(dict[str, object], self.stream_response.response)


class CliTests(unittest.TestCase):
    def test_handle_run_defaults_workspace_root_to_cwd(self) -> None:
        fake_client = _FakeClient()

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_run(
                    config_path="docs/architecture/runtime.example.toml",
                    objective="Inspect the repo",
                    workspace_roots=[],
                    constraints=[],
                    success_criteria=[],
                )
        self.assertEqual(exit_code, 0)
        request = fake_client.requests[0]
        self.assertEqual(
            request.params["task"]["workspace_roots"],  # type: ignore[attr-defined]
            [str(Path.cwd())],
        )
        self.assertIn("correlation_id=corr_1", stdout.getvalue())
        self.assertIn("hint=agent logs task_1", stdout.getvalue())

    def test_handle_status_renders_runtime_owned_snapshot(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
            "result": {
                "task": {
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "status": "completed",
                    "objective": "Inspect the repo",
                    "current_phase": "completed",
                    "latest_summary": "Summary created.",
                    "artifact_count": 1,
                    "failure": {"message": "ignored for completed"},
                }
            }
        }

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_status(
                    config_path="docs/architecture/runtime.example.toml",
                    task_id="task_1",
                    run_id="run_1",
                )
        self.assertEqual(exit_code, 0)
        self.assertIn("status=completed", stdout.getvalue())
        self.assertIn("latest_summary=Summary created.", stdout.getvalue())
        self.assertIn("artifact_count=1", stdout.getvalue())

    def test_handle_logs_renders_stream_ack_and_events(self) -> None:
        fake_client = _FakeClient()
        fake_client.stream_response = StreamResponse(
            response={
                "result": {
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "stream_open": True,
                }
            },
            events=[
                {
                    "type": "runtime.event",
                    "event": {"event_type": "task.started", "payload": {}},
                },
                {
                    "type": "runtime.event",
                    "event": {
                        "event_type": "subagent.started",
                        "payload": {
                            "runId": "run_1",
                            "subagentId": "researcher",
                            "taskDescription": "Inspect the repository structure.",
                            "timestamp": "2026-03-11T10:00:00Z",
                        },
                    },
                },
                {
                    "type": "runtime.event",
                    "event": {
                        "event_type": "subagent.completed",
                        "payload": {
                            "runId": "run_1",
                            "subagentId": "researcher",
                            "status": "success",
                            "duration": 0.42,
                            "timestamp": "2026-03-11T10:00:01Z",
                        },
                    },
                },
                {
                    "type": "runtime.event",
                    "event": {
                        "event_type": "artifact.created",
                        "payload": {"artifact": {"logical_path": "artifacts/repo_summary.md"}},
                    },
                },
            ],
        )

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_logs(
                    config_path="docs/architecture/runtime.example.toml",
                    task_id="task_1",
                    run_id="run_1",
                )
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        lines = output.strip().splitlines()
        self.assertIn("stream_open=True", lines[0])
        self.assertEqual(lines[1], "[task.started] execution started")
        self.assertEqual(
            lines[2],
            "[subagent.started] researcher taskDescription=Inspect the repository structure.",
        )
        self.assertEqual(
            lines[3],
            "[subagent.completed] researcher status=success duration=0.42",
        )
        self.assertEqual(lines[4], "[artifact.created] artifacts/repo_summary.md")

    def test_handle_artifacts_renders_runtime_artifact_metadata(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
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
            }
        }

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_artifacts(
                    config_path="docs/architecture/runtime.example.toml",
                    task_id="task_1",
                    run_id="run_1",
                )
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("artifact_id=artifact_1", output)
        self.assertIn("logical_path=artifacts/repo_summary.md", output)
        self.assertIn("persistence_class=run", output)

    def test_handle_resume_renders_updated_task_snapshot(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
            "result": {
                "task": {
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "status": "completed",
                    "objective": "Inspect the repo",
                    "current_phase": "completed",
                    "latest_summary": "Resumed successfully.",
                    "latest_checkpoint_id": "ckpt_2",
                }
            }
        }

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_resume(
                    config_path="docs/architecture/runtime.example.toml",
                    task_id="task_1",
                    run_id="run_1",
                )
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("status=completed", output)
        self.assertIn("latest_summary=Resumed successfully.", output)
        self.assertIn("latest_checkpoint_id=ckpt_2", output)

    def test_handle_approvals_renders_runtime_owned_approvals(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
            "result": {
                "approvals": [
                    {
                        "approval_id": "approval_1",
                        "status": "pending",
                        "type": "boundary",
                        "scope_summary": "file.write:workspace/**",
                        "description": "Allow write access",
                        "created_at": "2026-03-10T00:00:00Z",
                    }
                ]
            }
        }

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_approvals(
                    config_path="docs/architecture/runtime.example.toml",
                    task_id="task_1",
                    run_id="run_1",
                )
        self.assertEqual(exit_code, 0)
        self.assertIn("approval_id=approval_1", stdout.getvalue())
        self.assertIn("scope=file.write:workspace/**", stdout.getvalue())

    def test_handle_approve_accepts_runtime_snapshot(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
            "result": {
                "approval_id": "approval_1",
                "accepted": True,
                "status": "approved",
                "task": {
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "status": "completed",
                    "objective": "Inspect the repo",
                },
            }
        }

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_approve(
                    config_path="docs/architecture/runtime.example.toml",
                    task_id=None,
                    approval_id="approval_1",
                    decision="approve",
                    run_id="run_1",
                )
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("approval_id=approval_1 accepted=True status=approved", output)
        self.assertIn("status=completed", output)
        request = fake_client.requests[0]
        self.assertEqual(request.params["approval"]["decision"], "approved")  # type: ignore[attr-defined]

    def test_handle_diagnostics_renders_persisted_diagnostics(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
            "result": {
                "diagnostics": [
                    {
                        "diagnostic_id": "diag_1",
                        "kind": "policy_denied",
                        "created_at": "2026-03-10T00:00:00Z",
                        "message": "Network access denied",
                        "details": {"phase": "execute"},
                    }
                ]
            }
        }

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_diagnostics(
                    config_path="docs/architecture/runtime.example.toml",
                    task_id="task_1",
                    run_id="run_1",
                )
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("diagnostic_id=diag_1", output)
        self.assertIn("kind=policy_denied", output)

    def test_handle_memory_renders_entries(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
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
                        "provenance": {"task_id": "task_1"},
                    }
                ],
            }
        }

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_memory(
                    config_path="docs/architecture/runtime.example.toml",
                    task_id=None,
                    run_id=None,
                    scope="project",
                    namespace="project.conventions",
                )
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("scope=project", output)
        self.assertIn("memory_id=mem_1", output)
        self.assertIn('provenance={"task_id": "task_1"}', output)

    def test_handle_config_renders_redacted_effective_config(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
            "result": {
                "loaded_profiles": [],
                "config_sources": ["docs/architecture/runtime.example.toml"],
                "redactions": [{"path": "policy.api_token", "reason": "sensitive-key"}],
                "effective_config": {"policy": {"api_token": "***REDACTED***"}},
            }
        }

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_config("docs/architecture/runtime.example.toml")
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("redaction_count=1", output)
        self.assertIn('"api_token": "***REDACTED***"', output)


if __name__ == "__main__":
    unittest.main()
