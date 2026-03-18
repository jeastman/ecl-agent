from __future__ import annotations

import io
import unittest
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
    def test_handle_run_defaults_workspace_root_to_virtual_workspace(self) -> None:
        fake_client = _FakeClient()

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
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
            ["/workspace"],
        )
        self.assertIn("Task Accepted", stdout.getvalue())
        self.assertIn("corr_1", stdout.getvalue())
        self.assertIn("agent logs task_1", stdout.getvalue())

    def test_handle_run_uses_configured_default_workspace_root(self) -> None:
        fake_client = _FakeClient()

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch.object(cli, "_default_workspace_root", return_value="/workspace"):
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
            ["/workspace"],
        )
        self.assertIn("Task Accepted", stdout.getvalue())
        self.assertIn("corr_1", stdout.getvalue())
        self.assertIn("agent logs task_1", stdout.getvalue())

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
        self.assertIn("Task Status", stdout.getvalue())
        self.assertIn("completed", stdout.getvalue())
        self.assertIn("Summary created.", stdout.getvalue())
        self.assertIn("Artifacts", stdout.getvalue())
        self.assertIn("1", stdout.getvalue())

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
                        "payload": {
                            "artifact": {"logical_path": "/workspace/artifacts/repo_summary.md"}
                        },
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
        self.assertIn("Event Stream", output)
        self.assertIn("open", output)
        self.assertIn("task.started", output)
        self.assertIn("execution started", output)
        self.assertIn("researcher started: Inspect the repository structure.", output)
        self.assertIn("researcher status=success duration=0.42", output)
        self.assertIn("artifacts/repo_summary.md", output)

    def test_handle_artifacts_renders_runtime_artifact_metadata(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
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
        self.assertIn("Artifacts", output)
        self.assertIn("artifact_1", output)
        self.assertIn("artifacts/repo_summary.md", output)
        self.assertIn("run", output)

    def test_handle_skill_install_renders_runtime_result(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
            "result": {
                "status": "completed",
                "target_path": "/tmp/skills/repo-map",
                "approval_required": False,
                "summary": "Installed skill.",
                "validation": {
                    "status": "pass",
                    "findings": [],
                    "has_scripts": False,
                    "total_bytes": 20,
                    "file_count": 1,
                },
                "artifacts": ["/workspace/artifacts/skill-installs/repo-map/install-summary.json"],
            }
        }

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_skill_install(
                    config_path="docs/architecture/runtime.example.toml",
                    task_id="task_1",
                    run_id="run_1",
                    source_path="/repo-map",
                    target_scope="primary_agent",
                    target_role=None,
                    install_mode="fail_if_exists",
                    reason="Needed for repeated repo mapping work.",
                )
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("Skill Install", output)
        self.assertIn("completed", output)
        self.assertIn("False", output)
        request = fake_client.requests[0]
        self.assertEqual(request.method, "skill.install")  # type: ignore[attr-defined]
        self.assertEqual(request.params["task_id"], "task_1")  # type: ignore[attr-defined]

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
        self.assertIn("Task Resumed", output)
        self.assertIn("completed", output)
        self.assertIn("Resumed successfully.", output)
        self.assertIn("ckpt_2", output)

    def test_handle_reply_renders_updated_task_snapshot(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
            "result": {
                "task": {
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "status": "executing",
                    "objective": "Inspect the repo",
                    "current_phase": "executing",
                    "latest_summary": "Reply accepted.",
                }
            }
        }

        with patch.object(cli, "make_client", return_value=fake_client):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                exit_code = cli.handle_reply(
                    config_path="docs/architecture/runtime.example.toml",
                    task_id="task_1",
                    run_id="run_1",
                    message="Focus on docs only.",
                )
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("Task Reply Accepted", output)
        self.assertIn("Reply accepted.", output)
        request = fake_client.requests[0]
        self.assertEqual(request.method, "task.reply")  # type: ignore[attr-defined]
        self.assertEqual(request.params["message"], "Focus on docs only.")  # type: ignore[attr-defined]

    def test_handle_approvals_renders_runtime_owned_approvals(self) -> None:
        fake_client = _FakeClient()
        fake_client.response = {
            "result": {
                "approvals": [
                    {
                        "approval_id": "approval_1",
                        "status": "pending",
                        "type": "boundary",
                        "scope_summary": "file.write:/**",
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
        self.assertIn("Approvals", stdout.getvalue())
        self.assertIn("approval_1", stdout.getvalue())
        self.assertIn("file.write:/**", stdout.getvalue())

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
        self.assertIn("Approval Submitted", output)
        self.assertIn("approval_1", output)
        self.assertIn("True", output)
        self.assertIn("approved", output)
        self.assertIn("completed", output)
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
        self.assertIn("Diagnostics", output)
        self.assertIn("diag_1", output)
        self.assertIn("policy_denied", output)

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
        self.assertIn("Memory", output)
        self.assertIn("project", output)
        self.assertIn("mem_1", output)
        self.assertIn('{"task_id": "task_1"}', output)

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
        self.assertIn("Runtime Config", output)
        self.assertIn("1", output)
        self.assertIn('"api_token": "***REDACTED***"', output)


if __name__ == "__main__":
    unittest.main()
