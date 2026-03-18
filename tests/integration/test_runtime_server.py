from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
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
    METHOD_CONFIG_GET,
    METHOD_MEMORY_INSPECT,
    METHOD_SKILL_INSTALL,
    METHOD_TASK_APPROVE,
    METHOD_TASK_APPROVALS_LIST,
    METHOD_TASK_ARTIFACT_GET,
    METHOD_TASK_DIAGNOSTICS_LIST,
    METHOD_TASK_ARTIFACTS_LIST,
    METHOD_TASK_CREATE,
    METHOD_TASK_GET,
    METHOD_TASK_LIST,
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
        self.assertTrue(payload["result"]["capabilities"]["event_stream"])

    def test_runtime_task_flow_round_trip_with_registered_artifact(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            (workspace_root / "README.md").write_text("# Demo\n", encoding="utf-8")
            config = load_runtime_config(CONFIG_PATH)
            config.cli.default_workspace_root = str(workspace_root)
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
                        workspace_roots=["/workspace"],
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
            self.assertEqual(get_payload["result"]["task"]["artifact_count"], 2)
            self.assertNotIn("active_subagent", get_payload["result"]["task"])

            artifacts_request = JsonRpcRequest(
                method=METHOD_TASK_ARTIFACTS_LIST,
                params={"task_id": task_id, "run_id": run_id, "content_type_prefix": "text/"},
                id="3",
                correlation_id=correlation_id,
            )
            artifacts_response, _ = server.handle_line(json.dumps(artifacts_request.to_dict()))
            artifact_payload = artifacts_response.to_dict()["result"]["artifacts"]
            self.assertEqual(len(artifact_payload), 2)
            self.assertTrue(
                any(
                    artifact["logical_path"] == "/workspace/artifacts/repo_summary.md"
                    for artifact in artifact_payload
                )
            )

            artifact_get_request = JsonRpcRequest(
                method=METHOD_TASK_ARTIFACT_GET,
                params={
                    "task_id": task_id,
                    "run_id": run_id,
                    "artifact_id": next(
                        artifact["artifact_id"]
                        for artifact in artifact_payload
                        if artifact["logical_path"] == "/workspace/artifacts/repo_summary.md"
                    ),
                },
                id="3b",
                correlation_id=correlation_id,
            )
            artifact_get_response, _ = server.handle_line(
                json.dumps(artifact_get_request.to_dict())
            )
            artifact_get_payload = artifact_get_response.to_dict()["result"]
            self.assertEqual(
                artifact_get_payload["artifact"]["artifact_id"], artifact_payload[0]["artifact_id"]
            )
            self.assertEqual(artifact_get_payload["preview"]["kind"], "markdown")
            self.assertIn("#", artifact_get_payload["preview"]["text"])

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
            self.assertNotIn("subagent.started", event_types)
            self.assertNotIn("subagent.completed", event_types)
            self.assertIn("artifact.created", event_types)
            self.assertEqual(event_types[-1], "task.completed")
            artifact_event = next(
                event for event in stream_events if event.event.event_type == "artifact.created"
            )
            self.assertEqual(
                artifact_event.event.payload["artifact"]["logical_path"],
                "/workspace/artifacts/repo_summary.md",
            )
            self.assertEqual(
                artifact_event.event.payload["artifact"]["persistence_class"],
                "run",
            )

    def test_runtime_task_list_returns_recent_snapshots(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=_fake_langchain_harness(),
                runtime_root=str(Path(temp_dir) / "runtime"),
            )

            for request_id, objective in (("1", "First task"), ("2", "Second task")):
                create_request = JsonRpcRequest(
                    method=METHOD_TASK_CREATE,
                    params=TaskCreateParams(
                        task=TaskCreateRequest(
                            objective=objective,
                            workspace_roots=["/workspace"],
                        )
                    ).to_dict(),
                    id=request_id,
                    correlation_id=new_correlation_id(),
                )
                server.handle_line(json.dumps(create_request.to_dict()))

            list_request = JsonRpcRequest(
                method=METHOD_TASK_LIST,
                params={"limit": 10},
                id="3",
                correlation_id=new_correlation_id(),
            )
            list_response, _ = server.handle_line(json.dumps(list_request.to_dict()))
            payload = list_response.to_dict()["result"]
            self.assertEqual(payload["count"], 2)
            self.assertEqual(len(payload["tasks"]), 2)
            self.assertEqual(payload["tasks"][0]["objective"], "Second task")

    def test_runtime_server_streams_live_events_after_ack(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=_delayed_stream_harness(),
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            reader = _BlockingLineReader()
            writer = _CollectingWriter()
            serve_thread = threading.Thread(target=server.serve, args=(reader, writer))
            serve_thread.start()
            try:
                create_request = JsonRpcRequest(
                    method=METHOD_TASK_CREATE,
                    params=TaskCreateParams(
                        task=TaskCreateRequest(
                            objective="Inspect the repo",
                            workspace_roots=["/workspace"],
                        )
                    ).to_dict(),
                    id="1",
                    correlation_id=new_correlation_id(),
                )
                reader.push(json.dumps(create_request.to_dict()))
                create_payload = writer.wait_for_json(lambda payload: payload.get("id") == "1")
                task_id = create_payload["result"]["task_id"]
                run_id = create_payload["result"]["run_id"]

                logs_request = JsonRpcRequest(
                    method=METHOD_TASK_LOGS_STREAM,
                    params={"task_id": task_id, "run_id": run_id, "include_history": True},
                    id="2",
                    correlation_id=new_correlation_id(),
                )
                reader.push(json.dumps(logs_request.to_dict()))
                stream_open = writer.wait_for_json(lambda payload: payload.get("id") == "2")
                self.assertTrue(stream_open["result"]["stream_open"])
                started = writer.wait_for_json(
                    lambda payload: (
                        payload.get("type") == "runtime.event"
                        and payload["event"]["event_type"] == "task.started"
                    )
                )
                completed = writer.wait_for_json(
                    lambda payload: (
                        payload.get("type") == "runtime.event"
                        and payload["event"]["event_type"] == "task.completed"
                    )
                )
                self.assertEqual(started["event"]["task_id"], task_id)
                self.assertEqual(completed["event"]["run_id"], run_id)
            finally:
                reader.close()
                serve_thread.join(timeout=5)
                self.assertFalse(serve_thread.is_alive())

    def test_runtime_uses_configured_workspace_root_instead_of_process_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_root = temp_path / "config-root"
            config_root.mkdir()
            workspace_root = config_root / "workspace"
            workspace_root.mkdir()
            (workspace_root / "README.md").write_text("# Demo\n", encoding="utf-8")
            runtime_root = temp_path / "runtime"
            outside_cwd = temp_path / "other-cwd"
            outside_cwd.mkdir()
            config_path = config_root / "runtime.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[runtime]",
                        "name = 'local-agent-harness'",
                        "",
                        "[transport]",
                        "mode = 'stdio-jsonrpc'",
                        "",
                        "[cli]",
                        "default_workspace_root = './workspace'",
                        "",
                        "[identity]",
                        f"path = '{Path('agents/primary-agent/IDENTITY.md').resolve()}'",
                        "",
                        "[models.primary]",
                        "provider = 'openai'",
                        "model = 'gpt-5'",
                        "",
                        "[persistence]",
                        f"root_path = '{runtime_root}'",
                        "metadata_backend = 'sqlite'",
                        "event_backend = 'sqlite'",
                        "diagnostic_backend = 'sqlite'",
                    ]
                ),
                encoding="utf-8",
            )
            config = load_runtime_config(str(config_path))
            identity = load_identity_bundle(config.identity_path)

            original_cwd = Path.cwd()
            try:
                os.chdir(outside_cwd)
                server = create_runtime_server(
                    config=config,
                    identity=identity,
                    agent_harness=StubAgentHarness(),
                    runtime_root=str(runtime_root),
                )
                create_request = JsonRpcRequest(
                    method=METHOD_TASK_CREATE,
                    params=TaskCreateParams(
                        task=TaskCreateRequest(
                            objective="Inspect the repo",
                            workspace_roots=["/workspace"],
                        )
                    ).to_dict(),
                    id="cwd-mismatch",
                    correlation_id=new_correlation_id(),
                )

                create_response, _ = server.handle_line(json.dumps(create_request.to_dict()))
            finally:
                os.chdir(original_cwd)

            payload = create_response.to_dict()["result"]
            self.assertEqual(payload["status"], "accepted")

    def test_runtime_boots_with_real_phase3_harness_and_compiles_all_roles(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            (workspace_root / "README.md").write_text("# Demo\n", encoding="utf-8")
            config = load_runtime_config(CONFIG_PATH)
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            captures: dict[str, Any] = {}
            harness = LangChainDeepAgentHarness(
                model_name=config.primary_model.model,
                model_provider=config.primary_model.provider,
                model_factory=lambda model_name, *, model_provider: {
                    "model_name": model_name,
                    "model_provider": model_provider,
                },
                agent_factory=lambda **kwargs: _CapturingCompiledAgent(kwargs, captures),
            )
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=harness,
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            create_request = JsonRpcRequest(
                method=METHOD_TASK_CREATE,
                params=TaskCreateParams(
                    task=TaskCreateRequest(
                        objective="Inspect the repo",
                        workspace_roots=["/workspace"],
                    )
                ).to_dict(),
                id="phase3",
                correlation_id=new_correlation_id(),
            )

            create_response, _ = server.handle_line(json.dumps(create_request.to_dict()))
            payload = create_response.to_dict()["result"]

            self.assertEqual(payload["status"], "accepted")
            self.assertEqual(
                [subagent["name"] for subagent in captures["agent_kwargs"]["subagents"]],
                ["Coder", "Librarian", "Planner", "Researcher", "Verifier"],
            )
            researcher = next(
                subagent
                for subagent in captures["agent_kwargs"]["subagents"]
                if subagent["name"] == "Researcher"
            )
            self.assertEqual(researcher["model"]["model_name"], "gpt-5-mini")
            self.assertTrue((workspace_root / "artifacts" / "phase3-result.md").is_file())

            logs_request = JsonRpcRequest(
                method=METHOD_TASK_LOGS_STREAM,
                params={
                    "task_id": payload["task_id"],
                    "run_id": payload["run_id"],
                    "include_history": True,
                },
                id="phase3-logs",
                correlation_id=new_correlation_id(),
            )
            logs_response, stream_events = server.handle_line(json.dumps(logs_request.to_dict()))
            self.assertTrue(logs_response.to_dict()["result"]["stream_open"])
            started_event = next(
                event.event
                for event in stream_events
                if event.event.event_type == "subagent.started"
            )
            completed_event = next(
                event.event
                for event in stream_events
                if event.event.event_type == "subagent.completed"
            )
            self.assertEqual(started_event.payload["runId"], payload["run_id"])
            self.assertEqual(started_event.payload["subagentId"], "researcher")
            self.assertEqual(
                started_event.payload["taskDescription"],
                "Delegated researcher work for objective: Inspect the repo",
            )
            self.assertEqual(completed_event.payload["runId"], payload["run_id"])
            self.assertEqual(completed_event.payload["subagentId"], "researcher")
            self.assertEqual(completed_event.payload["status"], "success")
            self.assertGreaterEqual(completed_event.payload["duration"], 0.0)

    def test_skill_install_method_installs_primary_skill_and_next_run_discovers_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            staged_skill = workspace_root / "repo-map"
            staged_skill.mkdir()
            (staged_skill / "SKILL.md").write_text(
                "# Repo Map\nInstalled skill.\n", encoding="utf-8"
            )
            agent_root = _create_minimal_agent_tree(Path(temp_dir) / "agents")
            config = load_runtime_config(CONFIG_PATH)
            config.identity_path = str(agent_root / "primary-agent" / "IDENTITY.md")
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            harness = _SkillCaptureHarness()
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=harness,
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            create_request = JsonRpcRequest(
                method=METHOD_TASK_CREATE,
                params=TaskCreateParams(
                    task=TaskCreateRequest(
                        objective="Seed runtime context",
                        workspace_roots=["/workspace"],
                    )
                ).to_dict(),
                id="skill-create-1",
                correlation_id=new_correlation_id(),
            )
            create_response, _ = server.handle_line(json.dumps(create_request.to_dict()))
            created = create_response.to_dict()["result"]

            install_request = JsonRpcRequest(
                method=METHOD_SKILL_INSTALL,
                params={
                    "task_id": created["task_id"],
                    "run_id": created["run_id"],
                    "source_path": "/workspace/repo-map",
                    "target_scope": "primary_agent",
                    "install_mode": "fail_if_exists",
                    "reason": "Needed for recurring repository mapping work.",
                },
                id="skill-install-1",
                correlation_id=new_correlation_id(),
            )
            install_response, _ = server.handle_line(json.dumps(install_request.to_dict()))
            install_payload = install_response.to_dict()["result"]
            self.assertEqual(install_payload["status"], "completed")
            self.assertEqual(install_payload["validation"]["status"], "pass")
            self.assertTrue(
                (agent_root / "primary-agent" / "skills" / "repo-map" / "SKILL.md").is_file()
            )

            next_request = JsonRpcRequest(
                method=METHOD_TASK_CREATE,
                params=TaskCreateParams(
                    task=TaskCreateRequest(
                        objective="Use current primary skills",
                        workspace_roots=["/workspace"],
                    )
                ).to_dict(),
                id="skill-create-2",
                correlation_id=new_correlation_id(),
            )
            next_response, _ = server.handle_line(json.dumps(next_request.to_dict()))
            self.assertEqual(next_response.to_dict()["result"]["status"], "accepted")
            self.assertIn("repo-map", harness.last_primary_skill_ids)

    def test_skill_install_replace_requires_approval_and_completes_after_task_approve(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            staged_skill = workspace_root / "repo-map"
            staged_skill.mkdir()
            (staged_skill / "SKILL.md").write_text(
                "# Repo Map\nReplacement skill.\n", encoding="utf-8"
            )
            scripts_dir = staged_skill / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "install.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            agent_root = _create_minimal_agent_tree(Path(temp_dir) / "agents")
            existing_skill = agent_root / "primary-agent" / "skills" / "repo-map"
            existing_skill.mkdir(parents=True)
            (existing_skill / "SKILL.md").write_text("# Existing\n", encoding="utf-8")
            config = load_runtime_config(CONFIG_PATH)
            config.identity_path = str(agent_root / "primary-agent" / "IDENTITY.md")
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(),
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            create_request = JsonRpcRequest(
                method=METHOD_TASK_CREATE,
                params=TaskCreateParams(
                    task=TaskCreateRequest(
                        objective="Prepare install approval context",
                        workspace_roots=["/workspace"],
                    )
                ).to_dict(),
                id="replace-create",
                correlation_id=new_correlation_id(),
            )
            create_response, _ = server.handle_line(json.dumps(create_request.to_dict()))
            created = create_response.to_dict()["result"]

            install_request = JsonRpcRequest(
                method=METHOD_SKILL_INSTALL,
                params={
                    "task_id": created["task_id"],
                    "run_id": created["run_id"],
                    "source_path": "/workspace/repo-map",
                    "target_scope": "primary_agent",
                    "install_mode": "replace",
                    "reason": "Upgrade existing repo-map skill.",
                },
                id="replace-install",
                correlation_id=new_correlation_id(),
            )
            install_response, _ = server.handle_line(json.dumps(install_request.to_dict()))
            install_payload = install_response.to_dict()["result"]
            self.assertEqual(install_payload["status"], "approval_required")
            approval_id = install_payload["approval_id"]

            approve_request = JsonRpcRequest(
                method=METHOD_TASK_APPROVE,
                params={
                    "task_id": created["task_id"],
                    "run_id": created["run_id"],
                    "approval": {"approval_id": approval_id, "decision": "approved"},
                },
                id="replace-approve",
                correlation_id=new_correlation_id(),
            )
            approve_response, _ = server.handle_line(json.dumps(approve_request.to_dict()))
            approve_payload = approve_response.to_dict()["result"]
            self.assertTrue(approve_payload["accepted"])
            self.assertEqual(approve_payload["status"], "approved")
            self.assertIn(
                "Replacement skill.",
                (existing_skill / "SKILL.md").read_text(encoding="utf-8"),
            )

    def test_skill_install_method_installs_subagent_skill(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            staged_skill = workspace_root / "planner-kit"
            staged_skill.mkdir()
            (staged_skill / "SKILL.md").write_text("# Planner Kit\n", encoding="utf-8")
            agent_root = _create_minimal_agent_tree(Path(temp_dir) / "agents")
            config = load_runtime_config(CONFIG_PATH)
            config.identity_path = str(agent_root / "primary-agent" / "IDENTITY.md")
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(),
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            created = _create_task(server, workspace_root)
            install_request = JsonRpcRequest(
                method=METHOD_SKILL_INSTALL,
                params={
                    "task_id": created["task_id"],
                    "run_id": created["run_id"],
                    "source_path": "/workspace/planner-kit",
                    "target_scope": "subagent",
                    "target_role": "planner",
                    "install_mode": "fail_if_exists",
                    "reason": "Add reusable planner skill.",
                },
                id="subagent-install",
                correlation_id=new_correlation_id(),
            )
            install_response, _ = server.handle_line(json.dumps(install_request.to_dict()))
            install_payload = install_response.to_dict()["result"]
            self.assertEqual(install_payload["status"], "completed")
            self.assertTrue(
                (
                    agent_root / "subagents" / "planner" / "skills" / "planner-kit" / "SKILL.md"
                ).is_file()
            )

    def test_skill_install_returns_structured_failure_for_missing_skill_md(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            staged_skill = workspace_root / "broken-skill"
            staged_skill.mkdir()
            agent_root = _create_minimal_agent_tree(Path(temp_dir) / "agents")
            config = load_runtime_config(CONFIG_PATH)
            config.identity_path = str(agent_root / "primary-agent" / "IDENTITY.md")
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(),
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            created = _create_task(server, workspace_root)
            install_request = JsonRpcRequest(
                method=METHOD_SKILL_INSTALL,
                params={
                    "task_id": created["task_id"],
                    "run_id": created["run_id"],
                    "source_path": "/workspace/broken-skill",
                    "target_scope": "primary_agent",
                    "install_mode": "fail_if_exists",
                    "reason": "Try invalid skill.",
                },
                id="missing-skill-md",
                correlation_id=new_correlation_id(),
            )
            install_response, _ = server.handle_line(json.dumps(install_request.to_dict()))
            install_payload = install_response.to_dict()["result"]
            self.assertEqual(install_payload["status"], "failed")
            self.assertEqual(install_payload["validation"]["status"], "fail")
            self.assertTrue(
                any(
                    finding["code"] == "missing_skill_md"
                    for finding in install_payload["validation"]["findings"]
                )
            )

    def test_skill_install_returns_structured_failure_for_invalid_role(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            staged_skill = workspace_root / "repo-map"
            staged_skill.mkdir()
            (staged_skill / "SKILL.md").write_text("# Repo Map\n", encoding="utf-8")
            agent_root = _create_minimal_agent_tree(Path(temp_dir) / "agents")
            config = load_runtime_config(CONFIG_PATH)
            config.identity_path = str(agent_root / "primary-agent" / "IDENTITY.md")
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(),
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            created = _create_task(server, workspace_root)
            install_request = JsonRpcRequest(
                method=METHOD_SKILL_INSTALL,
                params={
                    "task_id": created["task_id"],
                    "run_id": created["run_id"],
                    "source_path": "/workspace/repo-map",
                    "target_scope": "subagent",
                    "target_role": "missing-role",
                    "install_mode": "fail_if_exists",
                    "reason": "Try invalid role.",
                },
                id="invalid-role",
                correlation_id=new_correlation_id(),
            )
            install_response, _ = server.handle_line(json.dumps(install_request.to_dict()))
            install_payload = install_response.to_dict()["result"]
            self.assertEqual(install_payload["status"], "failed")
            self.assertEqual(install_payload["validation"]["status"], "fail")
            self.assertIn("Unknown subagent role", install_payload["summary"])

    def test_skill_install_returns_structured_failure_for_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            agent_root = _create_minimal_agent_tree(Path(temp_dir) / "agents")
            config = load_runtime_config(CONFIG_PATH)
            config.identity_path = str(agent_root / "primary-agent" / "IDENTITY.md")
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(),
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            created = _create_task(server, workspace_root)
            install_request = JsonRpcRequest(
                method=METHOD_SKILL_INSTALL,
                params={
                    "task_id": created["task_id"],
                    "run_id": created["run_id"],
                    "source_path": "/workspace/../escape",
                    "target_scope": "primary_agent",
                    "install_mode": "fail_if_exists",
                    "reason": "Try traversal.",
                },
                id="path-traversal",
                correlation_id=new_correlation_id(),
            )
            install_response, _ = server.handle_line(json.dumps(install_request.to_dict()))
            install_payload = install_response.to_dict()["result"]
            self.assertEqual(install_payload["status"], "failed")
            self.assertEqual(install_payload["validation"]["status"], "fail")
            self.assertIn("traverse outside", install_payload["summary"])

    def test_runtime_persists_failed_subagent_completion_events(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            (workspace_root / "README.md").write_text("# Demo\n", encoding="utf-8")
            config = load_runtime_config(CONFIG_PATH)
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            captures: dict[str, Any] = {}
            harness = LangChainDeepAgentHarness(
                model_name=config.primary_model.model,
                model_provider=config.primary_model.provider,
                model_factory=lambda model_name, *, model_provider: {
                    "model_name": model_name,
                    "model_provider": model_provider,
                },
                agent_factory=lambda **kwargs: _FailingCompiledAgent(kwargs, captures),
            )
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=harness,
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            create_request = JsonRpcRequest(
                method=METHOD_TASK_CREATE,
                params=TaskCreateParams(
                    task=TaskCreateRequest(
                        objective="Inspect the repo",
                        workspace_roots=["/workspace"],
                    )
                ).to_dict(),
                id="phase3-failed",
                correlation_id=new_correlation_id(),
            )

            create_response, _ = server.handle_line(json.dumps(create_request.to_dict()))
            payload = create_response.to_dict()["result"]
            self.assertEqual(payload["status"], "accepted")

            logs_request = JsonRpcRequest(
                method=METHOD_TASK_LOGS_STREAM,
                params={
                    "task_id": payload["task_id"],
                    "run_id": payload["run_id"],
                    "include_history": True,
                },
                id="phase3-failed-logs",
                correlation_id=new_correlation_id(),
            )
            logs_response, stream_events = server.handle_line(json.dumps(logs_request.to_dict()))
            self.assertTrue(logs_response.to_dict()["result"]["stream_open"])
            started_event = next(
                event.event
                for event in stream_events
                if event.event.event_type == "subagent.started"
            )
            completed_event = next(
                event.event
                for event in stream_events
                if event.event.event_type == "subagent.completed"
            )
            failed_task_event = next(
                event.event for event in stream_events if event.event.event_type == "task.failed"
            )
            self.assertEqual(
                started_event.payload["taskDescription"],
                "Delegated researcher work for objective: Inspect the repo",
            )
            self.assertEqual(completed_event.payload["subagentId"], "researcher")
            self.assertEqual(completed_event.payload["status"], "failed")
            self.assertEqual(failed_task_event.payload["error"], "delegated failure")

    def test_runtime_server_streams_events_on_stdout_after_ack(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(output_artifact_path="/tmp/repo_summary.md"),
                runtime_root=str(Path(temp_dir) / "runtime"),
            )
            correlation_id = new_correlation_id()
            create_request = JsonRpcRequest(
                method=METHOD_TASK_CREATE,
                params=TaskCreateParams(
                    task=TaskCreateRequest(
                        objective="Inspect the repo",
                        workspace_roots=["/workspace"],
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
            config.cli.default_workspace_root = str(workspace_root)
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
                        workspace_roots=["/workspace"],
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
            config.cli.default_workspace_root = str(workspace_root)
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
            config.cli.default_workspace_root = str(workspace_root)
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

    def test_memory_inspect_supports_namespace_filter(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            config.cli.default_workspace_root = str(workspace_root)
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
                    memory_id="project_1",
                    scope="project",
                    namespace="project.conventions",
                    content="Convention",
                    summary="Convention",
                    provenance={"task_id": "task_1"},
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
            server.handlers.durable_services.memory_store.write_memory(
                MemoryRecord(
                    memory_id="project_2",
                    scope="project",
                    namespace="project.outcomes",
                    content="Outcome",
                    summary="Outcome",
                    provenance={"task_id": "task_1"},
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )

            response, _ = server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_MEMORY_INSPECT,
                        params={"scope": "project", "namespace": "project.outcomes"},
                        id="6",
                        correlation_id=new_correlation_id(),
                    ).to_dict()
                )
            )
            payload = response.to_dict()["result"]
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["entries"][0]["memory_id"], "project_2")

    def test_config_get_returns_redacted_effective_config(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            config = load_runtime_config(CONFIG_PATH)
            config.policy["api_token"] = "super-secret-token"
            identity = load_identity_bundle(config.identity_path)
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(),
                runtime_root=str(Path(temp_dir) / "runtime"),
                config_path=CONFIG_PATH,
            )

            response, _ = server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_CONFIG_GET,
                        params={},
                        id="7",
                        correlation_id=new_correlation_id(),
                    ).to_dict()
                )
            )
            payload = response.to_dict()["result"]
            self.assertEqual(
                payload["effective_config"]["models"]["default"],
                {"provider": "openai", "model": "gpt-5-nano"},
            )
            self.assertEqual(
                payload["effective_config"]["models"]["resolved"]["default"],
                {
                    "provider": "openai",
                    "model": "gpt-5-nano",
                    "profile_name": "default",
                    "source": "default_model",
                },
            )
            self.assertEqual(payload["effective_config"]["policy"]["api_token"], "***REDACTED***")
            self.assertEqual(
                payload["effective_config"]["models"]["resolved"]["primary"]["source"],
                "primary_model",
            )
            self.assertEqual(
                payload["effective_config"]["models"]["resolved"]["subagents"]["researcher"][
                    "source"
                ],
                "subagent_override",
            )
            self.assertEqual(
                payload["effective_config"]["subagents"]["planner"]["tool_bindings"],
                ["read_files", "memory_lookup", "plan_update"],
            )
            self.assertEqual(payload["effective_config"]["subagents"]["planner"]["skills"], [])
            self.assertEqual(payload["redactions"][0]["path"], "policy.api_token")
            self.assertIn(CONFIG_PATH, payload["config_sources"])

    def test_diagnostics_remain_available_after_restart(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            config.cli.default_workspace_root = str(workspace_root)
            identity = load_identity_bundle(config.identity_path)
            runtime_root = str(Path(temp_dir) / "runtime")
            correlation_id = new_correlation_id()

            first_server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=_network_denied_harness(),
                runtime_root=runtime_root,
            )
            create_request = JsonRpcRequest(
                method=METHOD_TASK_CREATE,
                params=TaskCreateParams(
                    task=TaskCreateRequest(
                        objective="Attempt denied network access",
                        workspace_roots=["/workspace"],
                    )
                ).to_dict(),
                id="8",
                correlation_id=correlation_id,
            )
            create_response, _ = first_server.handle_line(json.dumps(create_request.to_dict()))
            created = create_response.to_dict()["result"]
            task_id = created["task_id"]
            run_id = created["run_id"]

            recovered_server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=_network_denied_harness(),
                runtime_root=runtime_root,
            )
            diagnostics_response, _ = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_DIAGNOSTICS_LIST,
                        params={"task_id": task_id, "run_id": run_id},
                        id="9",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            payload = diagnostics_response.to_dict()["result"]
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["diagnostics"][0]["kind"], "tool_rejected")
            self.assertIn("details", payload["diagnostics"][0]["details"])

    def test_runtime_restart_recovers_paused_run_and_resumes_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            config.cli.default_workspace_root = str(workspace_root)
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
                        workspace_roots=["/workspace"],
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

            artifacts_response, _ = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_ARTIFACTS_LIST,
                        params={"task_id": task_id, "run_id": run_id},
                        id="6",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            artifacts = artifacts_response.to_dict()["result"]["artifacts"]
            self.assertEqual(len(artifacts), 1)

            artifact_get_response, _ = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_ARTIFACT_GET,
                        params={
                            "task_id": task_id,
                            "run_id": run_id,
                            "artifact_id": artifacts[0]["artifact_id"],
                        },
                        id="7",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            self.assertEqual(
                artifact_get_response.to_dict()["result"]["preview"]["kind"],
                "markdown",
            )

    def test_runtime_approval_round_trip_and_restart_recovery(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            config = load_runtime_config(CONFIG_PATH)
            config.cli.default_workspace_root = str(workspace_root)
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
                        workspace_roots=["/workspace"],
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

            approvals_response, _ = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_APPROVALS_LIST,
                        params={"task_id": task_id, "run_id": run_id},
                        id="3b",
                        correlation_id=correlation_id,
                    ).to_dict()
                )
            )
            approvals = approvals_response.to_dict()["result"]["approvals"]
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0]["approval_id"], approval_id)
            self.assertEqual(approvals[0]["status"], "pending")

            approve_response, _ = recovered_server.handle_line(
                json.dumps(
                    JsonRpcRequest(
                        method=METHOD_TASK_APPROVE,
                        params={
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
        listing = self._invoke("list_files", {"root": "/workspace"})
        readme = self._invoke("read_file", {"path": "/workspace/README.md"})
        self._invoke(
            "write_file",
            {
                "path": "/workspace/artifacts/repo_summary.md",
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
        request.sandbox.write_text("/workspace/artifacts/resumed.md", "# Recovered\n")
        return AgentExecutionResult(
            success=True,
            summary="Recovered run completed.",
            output_artifacts=["/workspace/artifacts/resumed.md"],
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
            artifact_store=request.artifact_store,
            memory_store=request.memory_store,
            on_event=on_event,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=bridge.authorize,
        )
        bindings.write_file("/workspace/apps/runtime/guarded.txt", "content\n")
        return AgentExecutionResult(
            success=True,
            summary="Governed write completed after approval.",
            output_artifacts=[],
        )


def _approval_harness() -> _ApprovalHarness:
    return _ApprovalHarness()


class _NetworkDeniedHarness:
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
            artifact_store=request.artifact_store,
            memory_store=request.memory_store,
            on_event=on_event,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=bridge.authorize,
        )
        bindings.execute_command(["curl", "https://example.com"], cwd="/workspace")
        return AgentExecutionResult(success=True, summary="unexpected", output_artifacts=[])


def _network_denied_harness() -> _NetworkDeniedHarness:
    return _NetworkDeniedHarness()


class _CapturingCompiledAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._tools = kwargs["tools"]
        self._subagents = kwargs.get("subagents") or []
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_payload"] = input
        self._captures["invoke_config"] = config
        for subagent in self._subagents:
            if subagent.get("name") == "Researcher":
                for middleware in subagent.get("middleware", []):
                    middleware.wrap_model_call(_FakeModelRequest(), lambda request: {"ok": True})
                break
        write_tool = next(tool for tool in self._tools if tool.name == "write_file")
        write_tool.invoke(
            {
                "path": "/workspace/artifacts/phase3-result.md",
                "content": "# Phase 3\n",
            }
        )
        return {"messages": [{"role": "assistant", "content": "Phase 3 execution complete."}]}


class _SkillCaptureHarness:
    def __init__(self) -> None:
        self.last_primary_skill_ids: list[str] = []

    def execute(self, request, on_event=None) -> Any:
        self.last_primary_skill_ids = [skill.skill_id for skill in request.primary_skills]
        return AgentExecutionResult(
            success=True,
            summary="Captured primary skills.",
            output_artifacts=[],
        )


class _FakeModelRequest:
    system_message = None


class _FailingCompiledAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._subagents = kwargs.get("subagents") or []
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_payload"] = input
        self._captures["invoke_config"] = config
        for subagent in self._subagents:
            if subagent.get("name") == "Researcher":
                for middleware in subagent.get("middleware", []):
                    middleware.wrap_model_call(
                        _FakeModelRequest(),
                        lambda request: (_ for _ in ()).throw(RuntimeError("delegated failure")),
                    )
        raise AssertionError("expected delegated failure to abort execution")


class _DelayedStreamHarness:
    def execute(self, request, on_event=None) -> Any:
        time.sleep(0.2)
        if on_event is not None:
            on_event(
                "plan.updated",
                {
                    "summary": "Planning underway.",
                    "current_step": "wait for stream",
                    "milestones": ["stream events"],
                },
            )
        time.sleep(0.2)
        return AgentExecutionResult(
            success=True,
            summary="Delayed execution complete.",
            output_artifacts=[],
        )


def _delayed_stream_harness() -> _DelayedStreamHarness:
    return _DelayedStreamHarness()


class _BlockingLineReader:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._lines: list[str] = []
        self._closed = False

    def push(self, line: str) -> None:
        with self._condition:
            self._lines.append(line + "\n")
            self._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def __iter__(self) -> "_BlockingLineReader":
        return self

    def __next__(self) -> str:
        with self._condition:
            while not self._lines and not self._closed:
                self._condition.wait(timeout=0.1)
            if self._lines:
                return self._lines.pop(0)
            raise StopIteration


class _CollectingWriter:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._lines: list[str] = []

    def write(self, data: str) -> int:
        with self._condition:
            self._lines.append(data)
            self._condition.notify_all()
        return len(data)

    def flush(self) -> None:
        return None

    def wait_for_json(self, predicate, timeout: float = 5.0) -> dict[str, Any]:
        deadline = time.time() + timeout
        index = 0
        with self._condition:
            while time.time() < deadline:
                while index < len(self._lines):
                    line = self._lines[index].strip()
                    index += 1
                    if not line:
                        continue
                    payload = json.loads(line)
                    if predicate(payload):
                        return payload
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=min(0.1, remaining))
        raise AssertionError("timed out waiting for matching JSON payload")


def _create_minimal_agent_tree(root: Path) -> Path:
    primary = root / "primary-agent"
    primary.mkdir(parents=True)
    (primary / "IDENTITY.md").write_text("# Primary Identity\n", encoding="utf-8")
    (primary / "skills").mkdir()
    subagent = root / "subagents" / "planner"
    subagent.mkdir(parents=True)
    (subagent / "manifest.yaml").write_text(
        "\n".join(
            [
                "role_id: planner",
                "name: Planner",
                "description: Planning role",
                "model_profile: planner",
                "tool_scope:",
                "  - read_files",
                "memory_scope:",
                "  - run",
                "filesystem_scope:",
                "  - workspace",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def _create_task(server, workspace_root: Path) -> dict[str, Any]:
    create_request = JsonRpcRequest(
        method=METHOD_TASK_CREATE,
        params=TaskCreateParams(
            task=TaskCreateRequest(
                objective="Create context",
                workspace_roots=["/workspace"],
            )
        ).to_dict(),
        id="helper-create",
        correlation_id=new_correlation_id(),
    )
    create_response, _ = server.handle_line(json.dumps(create_request.to_dict()))
    return create_response.to_dict()["result"]


if __name__ == "__main__":
    unittest.main()
