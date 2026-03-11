from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apps.runtime.local_agent_runtime.bootstrap import create_runtime_server
from apps.runtime.local_agent_runtime.task_runner import StubAgentHarness
from packages.config.local_agent_config.loader import load_runtime_config
from packages.identity.local_agent_identity.loader import load_identity_bundle
from packages.protocol.local_agent_protocol.models import (
    JsonRpcRequest,
    METHOD_TASK_ARTIFACTS_LIST,
    METHOD_TASK_CREATE,
    METHOD_TASK_GET,
    METHOD_TASK_LOGS_STREAM,
    PROTOCOL_VERSION,
    TaskCreateParams,
    TaskCreateRequest,
)
from packages.task_model.local_agent_task_model.ids import new_correlation_id


CONFIG_PATH = "docs/architecture/runtime.example.toml"


class RuntimeIntegrationTests(unittest.TestCase):
    def test_config_and_identity_load(self) -> None:
        config = load_runtime_config(CONFIG_PATH)
        identity = load_identity_bundle(config.identity_path)
        self.assertEqual(config.transport.mode, "stdio-jsonrpc")
        self.assertTrue(identity.version.startswith("sha256:"))

    def test_invalid_config_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "invalid.toml"
            config_path.write_text("[runtime]\nname = 'broken'\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing required table"):
                load_runtime_config(str(config_path))

    def test_missing_identity_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "identity file not found"):
            load_identity_bundle("/tmp/does-not-exist-identity.md")

    def test_runtime_health_round_trip(self) -> None:
        request = JsonRpcRequest(
            method="runtime.health",
            params={},
            id="1",
            correlation_id=new_correlation_id(),
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "apps.runtime.local_agent_runtime.main",
                "--config",
                CONFIG_PATH,
            ],
            input=json.dumps(request.to_dict()) + "\n",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout.strip())
        self.assertEqual(payload["result"]["status"], "ok")
        self.assertEqual(payload["correlation_id"], request.correlation_id)
        self.assertEqual(payload["result"]["protocol_version"], PROTOCOL_VERSION)

    def test_runtime_task_flow_round_trip_with_registered_artifact(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(output_artifact_path="scratch/repo_summary.md"),
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            correlation_id = new_correlation_id()
            create_request = JsonRpcRequest(
                method=METHOD_TASK_CREATE,
                params=TaskCreateParams(
                    task=TaskCreateRequest(
                        objective="Inspect the repo",
                        workspace_roots=[str(workspace_root)],
                    )
                ).to_dict(),
                id="1",
                correlation_id=correlation_id,
            )
            create_response, _ = server.handle_line(json.dumps(create_request.to_dict()))
            create_payload = create_response.to_dict()
            task_id = create_payload["result"]["task_id"]
            run_id = create_payload["result"]["run_id"]
            self.assertEqual(create_payload["result"]["status"], "accepted")

            get_request = JsonRpcRequest(
                method=METHOD_TASK_GET,
                params={"task_id": task_id, "run_id": run_id},
                id="2",
                correlation_id=correlation_id,
            )
            get_response, _ = server.handle_line(json.dumps(get_request.to_dict()))
            get_payload = get_response.to_dict()
            self.assertEqual(get_payload["result"]["task"]["task_id"], task_id)
            self.assertEqual(get_payload["result"]["task"]["artifact_count"], 1)

            artifacts_request = JsonRpcRequest(
                method=METHOD_TASK_ARTIFACTS_LIST,
                params={"task_id": task_id, "run_id": run_id, "content_type_prefix": "text/"},
                id="3",
                correlation_id=correlation_id,
            )
            artifacts_response, _ = server.handle_line(json.dumps(artifacts_request.to_dict()))
            artifact_payload = artifacts_response.to_dict()["result"]["artifacts"]
            self.assertEqual(len(artifact_payload), 1)
            self.assertEqual(artifact_payload[0]["logical_path"], "scratch/repo_summary.md")

            logs_request = JsonRpcRequest(
                method=METHOD_TASK_LOGS_STREAM,
                params={"task_id": task_id, "run_id": run_id, "include_history": True},
                id="4",
                correlation_id=correlation_id,
            )
            logs_response, stream_events = server.handle_line(json.dumps(logs_request.to_dict()))
            logs_payload = logs_response.to_dict()
            self.assertTrue(logs_payload["result"]["stream_open"])
            self.assertEqual(logs_payload["result"]["run_id"], run_id)
            self.assertEqual(
                [event.event.event_type for event in stream_events],
                ["task.created", "task.started", "artifact.created", "task.completed"],
            )
            self.assertEqual(
                stream_events[2].event.payload["artifact"]["logical_path"],
                "scratch/repo_summary.md",
            )
            self.assertEqual(
                stream_events[2].event.payload["artifact"]["persistence_class"],
                "ephemeral",
            )

    def test_runtime_server_streams_events_on_stdout_after_ack(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(output_artifact_path="scratch/repo_summary.md"),
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            correlation_id = new_correlation_id()
            create_request = JsonRpcRequest(
                method=METHOD_TASK_CREATE,
                params=TaskCreateParams(
                    task=TaskCreateRequest(
                        objective="Inspect the repo",
                        workspace_roots=[str(workspace_root)],
                    )
                ).to_dict(),
                id="1",
                correlation_id=correlation_id,
            )
            create_response, _ = server.handle_line(json.dumps(create_request.to_dict()))
            task_id = create_response.to_dict()["result"]["task_id"]
            run_id = create_response.to_dict()["result"]["run_id"]

            logs_request = JsonRpcRequest(
                method=METHOD_TASK_LOGS_STREAM,
                params={"task_id": task_id, "run_id": run_id, "include_history": True},
                id="2",
                correlation_id=correlation_id,
            )
            reader = io.StringIO(json.dumps(logs_request.to_dict()) + "\n")
            writer = io.StringIO()
            server.serve(reader, writer)
            output_lines = [json.loads(line) for line in writer.getvalue().strip().splitlines()]
            self.assertEqual(output_lines[0]["result"]["stream_open"], True)
            self.assertEqual(output_lines[1]["type"], "runtime.event")
            self.assertEqual(output_lines[1]["event"]["event_type"], "task.created")


if __name__ == "__main__":
    unittest.main()
