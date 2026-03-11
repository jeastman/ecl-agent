from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apps.runtime.local_agent_runtime.artifact_store import InMemoryArtifactStore
from apps.runtime.local_agent_runtime.bootstrap import create_runtime_server
from apps.runtime.local_agent_runtime.event_bus import InMemoryEventBus
from apps.runtime.local_agent_runtime.run_state_store import InMemoryRunStateStore
from apps.runtime.local_agent_runtime.task_runner import StubAgentHarness, TaskRunner
from packages.config.local_agent_config.loader import load_runtime_config
from packages.identity.local_agent_identity.loader import load_identity_bundle
from packages.protocol.local_agent_protocol.models import (
    EventEnvelope,
    EventSource,
    EventSourceKind,
    JsonRpcRequest,
    METHOD_TASK_ARTIFACTS_LIST,
    METHOD_TASK_CREATE,
    METHOD_TASK_GET,
    METHOD_TASK_LOGS_STREAM,
    PROTOCOL_VERSION,
    RuntimeEvent,
    TaskArtifactsListParams,
    TaskCreateParams,
    TaskCreateRequest,
    TaskGetParams,
    TaskLogsStreamParams,
    TaskSnapshot,
    utc_now_timestamp,
)
from packages.task_model.local_agent_task_model.ids import new_correlation_id
from packages.task_model.local_agent_task_model.models import EventType, TaskStatus


CONFIG_PATH = "docs/architecture/runtime.example.toml"


class ProtocolModelTests(unittest.TestCase):
    def test_task_create_params_round_trip(self) -> None:
        params = TaskCreateParams(
            task=TaskCreateRequest(
                objective="Inspect the repo",
                workspace_roots=["."],
                constraints=["stay in repo"],
                success_criteria=["return a summary"],
            )
        )
        parsed = TaskCreateParams.from_dict(params.to_dict())
        self.assertEqual(parsed.task.objective, "Inspect the repo")
        self.assertEqual(parsed.task.workspace_roots, ["."])

    def test_task_snapshot_serialization_omits_none(self) -> None:
        snapshot = TaskSnapshot(
            task_id="task_1",
            run_id="run_1",
            status=TaskStatus.EXECUTING,
            objective="Inspect the repo",
            created_at=utc_now_timestamp(),
            updated_at=utc_now_timestamp(),
            links={"events": METHOD_TASK_LOGS_STREAM},
        )
        payload = snapshot.to_dict()
        self.assertEqual(payload["status"], "executing")
        self.assertNotIn("failure", payload)
        self.assertEqual(payload["links"]["events"], METHOD_TASK_LOGS_STREAM)

    def test_task_query_params_validate(self) -> None:
        self.assertEqual(TaskGetParams.from_dict({"task_id": "task_1"}).task_id, "task_1")
        self.assertEqual(
            TaskArtifactsListParams.from_dict({"task_id": "task_1"}).task_id,
            "task_1",
        )
        self.assertTrue(
            TaskLogsStreamParams.from_dict(
                {"task_id": "task_1", "include_history": True}
            ).include_history
        )

    def test_runtime_event_serialization(self) -> None:
        event = RuntimeEvent(
            event=EventEnvelope(
                event_id="evt_1",
                event_type=EventType.TASK_CREATED.value,
                timestamp=utc_now_timestamp(),
                correlation_id="corr_1",
                task_id="task_1",
                run_id="run_1",
                source=EventSource(kind=EventSourceKind.RUNTIME, component="tests"),
                payload={"status": "created"},
            )
        )
        payload = event.to_dict()
        self.assertEqual(payload["type"], "runtime.event")
        self.assertEqual(payload["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(payload["event"]["source"]["component"], "tests")


class RunStateStoreTests(unittest.TestCase):
    def test_create_get_and_update_state(self) -> None:
        store = InMemoryRunStateStore()
        runner = TaskRunner(
            run_state_store=store,
            event_bus=InMemoryEventBus(),
            artifact_store=InMemoryArtifactStore(),
            agent_harness=StubAgentHarness(),
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=["."],
            identity_bundle_text="identity",
        )
        state = store.get(task_id, run_id)
        self.assertEqual(state.status, TaskStatus.COMPLETED)
        self.assertEqual(state.workspace_roots, ["."])
        self.assertEqual(state.current_phase, "completed")
        self.assertIsNotNone(state.last_event_at)

    def test_missing_task_raises(self) -> None:
        store = InMemoryRunStateStore()
        with self.assertRaisesRegex(KeyError, "unknown task"):
            store.get("task_missing")


class EventBusTests(unittest.TestCase):
    def test_list_events_preserves_order_and_replay(self) -> None:
        bus = InMemoryEventBus()
        first = RuntimeEvent(
            event=EventEnvelope(
                event_id="evt_1",
                event_type=EventType.TASK_CREATED.value,
                timestamp=utc_now_timestamp(),
                correlation_id="corr_1",
                task_id="task_1",
                run_id="run_1",
                source=EventSource(kind=EventSourceKind.RUNTIME, component="tests"),
                payload={"status": "created"},
            )
        )
        second = RuntimeEvent(
            event=EventEnvelope(
                event_id="evt_2",
                event_type=EventType.TASK_STARTED.value,
                timestamp=utc_now_timestamp(),
                correlation_id="corr_1",
                task_id="task_1",
                run_id="run_1",
                source=EventSource(kind=EventSourceKind.RUNTIME, component="tests"),
                payload={"status": "executing"},
            )
        )
        bus.publish(first)
        bus.publish(second)
        events = bus.list_events("task_1", "run_1")
        replay = bus.list_events("task_1", "run_1", from_event_id="evt_1")
        self.assertEqual([event.event.event_id for event in events], ["evt_1", "evt_2"])
        self.assertEqual([event.event.event_id for event in replay], ["evt_2"])


class TaskRunnerTests(unittest.TestCase):
    def test_task_runner_emits_expected_event_order_on_success(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(),
            agent_harness=StubAgentHarness(),
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=["."],
            identity_bundle_text="identity",
        )
        event_types = [event.event.event_type for event in bus.list_events(task_id, run_id)]
        self.assertEqual(
            event_types,
            ["task.created", "task.started", "task.completed"],
        )
        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.COMPLETED)

    def test_task_runner_records_failure(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(),
            agent_harness=StubAgentHarness(success=False),
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=["."],
            identity_bundle_text="identity",
        )
        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.FAILED)
        self.assertEqual(bus.list_events(task_id, run_id)[-1].event.event_type, "task.failed")


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
            [sys.executable, "-m", "apps.runtime.local_agent_runtime.main", "--config", CONFIG_PATH],
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

    def test_runtime_task_flow_round_trip(self) -> None:
        config = load_runtime_config(CONFIG_PATH)
        identity = load_identity_bundle(config.identity_path)
        server = create_runtime_server(config=config, identity=identity)
        correlation_id = new_correlation_id()
        create_request = JsonRpcRequest(
            method=METHOD_TASK_CREATE,
            params=TaskCreateParams(
                task=TaskCreateRequest(objective="Inspect the repo", workspace_roots=["."])
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
        self.assertEqual(get_payload["result"]["task"]["links"]["events"], METHOD_TASK_LOGS_STREAM)

        artifacts_request = JsonRpcRequest(
            method=METHOD_TASK_ARTIFACTS_LIST,
            params={"task_id": task_id, "run_id": run_id},
            id="3",
            correlation_id=correlation_id,
        )
        artifacts_response, _ = server.handle_line(json.dumps(artifacts_request.to_dict()))
        self.assertEqual(artifacts_response.to_dict()["result"]["artifacts"], [])

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
            ["task.created", "task.started", "task.completed"],
        )

    def test_runtime_server_streams_events_on_stdout_after_ack(self) -> None:
        config = load_runtime_config(CONFIG_PATH)
        identity = load_identity_bundle(config.identity_path)
        server = create_runtime_server(config=config, identity=identity)
        correlation_id = new_correlation_id()
        create_request = JsonRpcRequest(
            method=METHOD_TASK_CREATE,
            params=TaskCreateParams(
                task=TaskCreateRequest(objective="Inspect the repo", workspace_roots=["."])
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
