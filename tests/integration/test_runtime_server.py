from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from apps.runtime.local_agent_runtime.bootstrap import create_runtime_server
from apps.runtime.local_agent_runtime.task_runner import AgentExecutionResult
from apps.runtime.local_agent_runtime.task_runner import StubAgentHarness
from packages.config.local_agent_config.loader import load_runtime_config
from packages.identity.local_agent_identity.loader import load_identity_bundle
from packages.protocol.local_agent_protocol.models import (
    JsonRpcRequest,
    METHOD_MEMORY_INSPECT,
    METHOD_TASK_APPROVE,
    METHOD_TASK_ARTIFACTS_LIST,
    METHOD_TASK_CREATE,
    METHOD_TASK_GET,
    METHOD_TASK_LOGS_STREAM,
    METHOD_TASK_RESUME,
    PROTOCOL_VERSION,
    TaskCreateParams,
    TaskCreateRequest,
    utc_now_timestamp,
)
from packages.task_model.local_agent_task_model.ids import new_correlation_id
from services.memory_service.local_agent_memory_service.memory_models import MemoryRecord
from services.deepagent_runtime.local_agent_deepagent_runtime.deepagent_harness import (
    LangChainDeepAgentHarness,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.tool_bindings import (
    SandboxToolBindings,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.interrupt_bridge import (
    InterruptBridge,
)


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
            (workspace_root / "README.md").write_text("# Demo\n", encoding="utf-8")
            config = load_runtime_config(CONFIG_PATH)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=_fake_langchain_harness(),
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
            self.assertEqual(get_payload["result"]["task"]["active_subagent"], "primary")

            artifacts_request = JsonRpcRequest(
                method=METHOD_TASK_ARTIFACTS_LIST,
                params={"task_id": task_id, "run_id": run_id, "content_type_prefix": "text/"},
                id="3",
                correlation_id=correlation_id,
            )
            artifacts_response, _ = server.handle_line(json.dumps(artifacts_request.to_dict()))
            artifact_payload = artifacts_response.to_dict()["result"]["artifacts"]
            self.assertEqual(len(artifact_payload), 1)
            self.assertEqual(artifact_payload[0]["logical_path"], "artifacts/repo_summary.md")

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
            event_types = [event.event.event_type for event in stream_events]
            self.assertEqual(event_types[0:2], ["task.created", "task.started"])
            self.assertIn("plan.updated", event_types)
            self.assertIn("subagent.started", event_types)
            self.assertIn("artifact.created", event_types)
            self.assertEqual(event_types[-1], "task.completed")
            artifact_event = next(
                event for event in stream_events if event.event.event_type == "artifact.created"
            )
            self.assertEqual(
                artifact_event.event.payload["artifact"]["logical_path"],
                "artifacts/repo_summary.md",
            )
            self.assertEqual(
                artifact_event.event.payload["artifact"]["persistence_class"],
                "run",
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

    def test_memory_inspect_returns_project_and_run_state_by_default(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(),
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
            created = create_response.to_dict()["result"]
            task_id = created["task_id"]
            run_id = created["run_id"]
            memory_store = server.handlers.durable_services.memory_store
            timestamp = utc_now_timestamp()
            memory_store.write_memory(
                MemoryRecord(
                    memory_id="project_1",
                    scope="project",
                    namespace="project.conventions",
                    content="Prefer explicit dataclasses.",
                    summary="Convention",
                    provenance={"task_id": task_id},
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
            memory_store.write_memory(
                MemoryRecord(
                    memory_id="run_1",
                    scope="run_state",
                    namespace="run.notes",
                    content="Observed useful detail.",
                    summary="Run note",
                    provenance={"task_id": task_id, "run_id": run_id},
                    created_at=timestamp,
                    updated_at=timestamp,
                    source_run=run_id,
                )
            )
            memory_store.write_memory(
                MemoryRecord(
                    memory_id="scratch_1",
                    scope="scratch",
                    namespace="scratch.notes",
                    content="Do not show by default.",
                    summary="Scratch",
                    provenance={"task_id": task_id, "run_id": run_id},
                    created_at=timestamp,
                    updated_at=timestamp,
                    source_run=run_id,
                )
            )

            inspect_response, _ = server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_MEMORY_INSPECT,
                        params={"task_id": task_id, "run_id": run_id},
                        id="2",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            payload = inspect_response.to_dict()["result"]
            self.assertEqual(payload["scope"], "default")
            self.assertEqual(payload["count"], 2)
            self.assertEqual(
                {entry["memory_id"] for entry in payload["entries"]},
                {"project_1", "run_1"},
            )

    def test_memory_inspect_supports_identity_scope_and_restart_persistence(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            runtime_root = str(Path(temp_dir) / "runtime")
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(),
                runtime_root=runtime_root,
            )
            timestamp = utc_now_timestamp()
            server.handlers.durable_services.memory_store.write_memory(
                MemoryRecord(
                    memory_id="project_1",
                    scope="project",
                    namespace="project.outcomes",
                    content="Outcome persisted across restart.",
                    summary="Outcome",
                    provenance={"task_id": "task_1"},
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )

            recovered_server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(),
                runtime_root=runtime_root,
            )

            identity_response, _ = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_MEMORY_INSPECT,
                        params={"scope": "identity"},
                        id="3",
                        correlation_id=new_correlation_id(),
                    ).to_dict()
                )
            )
            identity_payload = identity_response.to_dict()["result"]
            self.assertEqual(identity_payload["count"], 1)
            self.assertEqual(identity_payload["entries"][0]["scope"], "identity")

            project_response, _ = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_MEMORY_INSPECT,
                        params={"scope": "project"},
                        id="4",
                        correlation_id=new_correlation_id(),
                    ).to_dict()
                )
            )
            project_payload = project_response.to_dict()["result"]
            self.assertEqual(project_payload["count"], 1)
            self.assertEqual(project_payload["entries"][0]["memory_id"], "project_1")

    def test_memory_inspect_returns_scratch_only_when_explicitly_requested(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(),
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            timestamp = utc_now_timestamp()
            server.handlers.durable_services.memory_store.write_memory(
                MemoryRecord(
                    memory_id="scratch_1",
                    scope="scratch",
                    namespace="scratch.notes",
                    content="Scratch detail",
                    summary="Scratch detail",
                    provenance={"task_id": "task_1", "run_id": "run_1"},
                    created_at=timestamp,
                    updated_at=timestamp,
                    source_run="run_1",
                )
            )

            response, _ = server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_MEMORY_INSPECT,
                        params={"scope": "scratch", "task_id": "task_1", "run_id": "run_1"},
                        id="5",
                        correlation_id=new_correlation_id(),
                    ).to_dict()
                )
            )
            payload = response.to_dict()["result"]
            self.assertEqual(payload["scope"], "scratch")
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["entries"][0]["namespace"], "scratch.notes")

    def test_runtime_restart_recovers_paused_run_and_resumes_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            identity = load_identity_bundle(config.identity_path)
            runtime_root = str(Path(temp_dir) / "runtime")
            correlation_id = new_correlation_id()

            first_server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=_pause_then_resume_harness(),
                runtime_root=runtime_root,
            )
            create_request = JsonRpcRequest(
                method=METHOD_TASK_CREATE,
                params=TaskCreateParams(
                    task=TaskCreateRequest(
                        objective="Pause and resume the repo task",
                        workspace_roots=[str(workspace_root)],
                    )
                ).to_dict(),
                id="1",
                correlation_id=correlation_id,
            )
            create_response, _ = first_server.handle_line(json.dumps(create_request.to_dict()))
            created = create_response.to_dict()["result"]
            task_id = created["task_id"]
            run_id = created["run_id"]

            paused_response, _ = first_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_GET,
                        params={"task_id": task_id, "run_id": run_id},
                        id="2",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            self.assertEqual(paused_response.to_dict()["result"]["task"]["status"], "paused")

            recovered_server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=_pause_then_resume_harness(),
                runtime_root=runtime_root,
            )
            recovered_status, _ = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_GET,
                        params={"task_id": task_id, "run_id": run_id},
                        id="3",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            recovered_task = recovered_status.to_dict()["result"]["task"]
            self.assertEqual(recovered_task["status"], "paused")
            self.assertTrue(recovered_task["is_resumable"])
            self.assertIsNotNone(recovered_task["latest_checkpoint_id"])
            self.assertEqual(recovered_task["links"]["resume"], "task.resume")
            self.assertEqual(recovered_task["latest_summary"], "Paused awaiting resume.")

            resumed_response, _ = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_RESUME,
                        params={"task_id": task_id, "run_id": run_id},
                        id="4",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            resumed_task = resumed_response.to_dict()["result"]["task"]
            self.assertEqual(resumed_task["status"], "completed")
            self.assertEqual(resumed_task["artifact_count"], 1)

            logs_response, stream_events = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_LOGS_STREAM,
                        params={"task_id": task_id, "run_id": run_id, "include_history": True},
                        id="5",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            self.assertTrue(logs_response.to_dict()["result"]["stream_open"])
            event_types = [event.event.event_type for event in stream_events]
            self.assertIn("task.paused", event_types)
            self.assertIn("recovery.discovered", event_types)
            self.assertIn("task.resumed", event_types)
            self.assertIn("task.completed", event_types)

    def test_runtime_approval_round_trip_and_restart_recovery(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            identity = load_identity_bundle(config.identity_path)
            runtime_root = str(Path(temp_dir) / "runtime")
            correlation_id = new_correlation_id()

            first_server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=_approval_harness(),
                runtime_root=runtime_root,
            )
            create_request = JsonRpcRequest(
                method=METHOD_TASK_CREATE,
                params=TaskCreateParams(
                    task=TaskCreateRequest(
                        objective="Edit governed files",
                        workspace_roots=[str(workspace_root)],
                    )
                ).to_dict(),
                id="1",
                correlation_id=correlation_id,
            )
            create_response, _ = first_server.handle_line(json.dumps(create_request.to_dict()))
            created = create_response.to_dict()["result"]
            task_id = created["task_id"]
            run_id = created["run_id"]

            pending_response, _ = first_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_GET,
                        params={"task_id": task_id, "run_id": run_id},
                        id="2",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            pending_task = pending_response.to_dict()["result"]["task"]
            self.assertEqual(pending_task["status"], "awaiting_approval")
            approval_id = pending_task["pending_approval_id"]
            self.assertIsNotNone(approval_id)

            recovered_server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=_approval_harness(),
                runtime_root=runtime_root,
            )
            recovered_response, _ = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_GET,
                        params={"task_id": task_id, "run_id": run_id},
                        id="3",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            recovered_task = recovered_response.to_dict()["result"]["task"]
            self.assertEqual(recovered_task["status"], "awaiting_approval")
            self.assertEqual(recovered_task["pending_approval_id"], approval_id)
            self.assertEqual(recovered_task["links"]["approve"], "task.approve")

            approve_response, _ = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_APPROVE,
                        params={
                            "task_id": task_id,
                            "run_id": run_id,
                            "approval": {
                                "approval_id": approval_id,
                                "decision": "approved",
                            },
                        },
                        id="4",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            approved_payload = approve_response.to_dict()["result"]
            self.assertTrue(approved_payload["accepted"])
            self.assertEqual(approved_payload["status"], "approved")
            self.assertEqual(approved_payload["task"]["status"], "completed")

            logs_response, stream_events = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_LOGS_STREAM,
                        params={"task_id": task_id, "run_id": run_id, "include_history": True},
                        id="5",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            self.assertTrue(logs_response.to_dict()["result"]["stream_open"])
            event_types = [event.event.event_type for event in stream_events]
            self.assertEqual(event_types.count("approval.requested"), 1)
            self.assertIn("task.resumed", event_types)
            self.assertIn("task.completed", event_types)


def _fake_langchain_harness() -> LangChainDeepAgentHarness:
    return LangChainDeepAgentHarness(
        model_name="gpt-5",
        model_provider="openai",
        model_factory=lambda model_name, model_provider: {
            "model_name": model_name,
            "model_provider": model_provider,
        },
        agent_factory=lambda **kwargs: _FakeCompiledAgent(kwargs["tools"]),
    )


class _FakeCompiledAgent:
    def __init__(self, tools: list[Any]) -> None:
        self._tools = tools

    def invoke(
        self,
        input: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        listing = self._invoke("list_files", {"root": "workspace"})
        readme = self._invoke("read_file", {"path": "workspace/README.md"})
        self._invoke(
            "write_file",
            {
                "path": "workspace/artifacts/repo_summary.md",
                "content": "\n".join(
                    [
                        "# Repository Architecture Summary",
                        "",
                        f"Files observed: {len(listing)}",
                        f"First line: {readme.splitlines()[0]}",
                    ]
                )
                + "\n",
            },
        )
        return {"messages": [{"role": "assistant", "content": "Summary created."}]}

    def _invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        for tool in self._tools:
            if tool.name == name:
                return tool.invoke(arguments)
        raise AssertionError(f"missing tool: {name}")


class _PauseThenResumeHarness:
    def execute(self, request, on_event=None) -> Any:
        controller = request.checkpoint_controller
        if controller is None:
            raise AssertionError("checkpoint controller is required")
        if request.resume_from_checkpoint_id is None:
            metadata = controller.record_checkpoint("pause_requested")
            if on_event is not None:
                on_event("checkpoint.saved", metadata.to_dict())
            return AgentExecutionResult(
                success=False,
                summary="Paused awaiting resume.",
                output_artifacts=[],
                error_message=None,
                paused=True,
                pause_reason="awaiting resume",
            )
        metadata = controller.record_checkpoint("resumed")
        if on_event is not None:
            on_event("checkpoint.saved", metadata.to_dict())
        request.sandbox.write_text("workspace/artifacts/resumed.md", "# Recovered\n")
        return AgentExecutionResult(
            success=True,
            summary="Recovered run completed.",
            output_artifacts=["workspace/artifacts/resumed.md"],
            error_message=None,
            paused=False,
            pause_reason=None,
        )


def _pause_then_resume_harness() -> _PauseThenResumeHarness:
    return _PauseThenResumeHarness()


class _ApprovalHarness:
    def execute(self, request, on_event=None) -> Any:
        bridge = InterruptBridge(
            governed_operation=request.governed_operation,
            checkpoint_controller=request.checkpoint_controller,
            on_event=on_event,
        )
        bindings = SandboxToolBindings(
            sandbox=request.sandbox,
            task_id=request.task_id,
            run_id=request.run_id,
            on_event=on_event,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=bridge.authorize,
        )
        bindings.write_file("workspace/apps/runtime/guarded.txt", "content\n")
        return AgentExecutionResult(
            success=True,
            summary="Governed write completed after approval.",
            output_artifacts=[],
        )


def _approval_harness() -> _ApprovalHarness:
    return _ApprovalHarness()


if __name__ == "__main__":
    unittest.main()
