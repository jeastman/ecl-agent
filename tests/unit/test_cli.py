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
                    "active_subagent": "primary",
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
        self.assertIn("active_subagent=primary", stdout.getvalue())
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
        self.assertEqual(lines[2], "[artifact.created] artifacts/repo_summary.md")

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


if __name__ == "__main__":
    unittest.main()
