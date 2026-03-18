from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
from typing import Any, cast
from unittest.mock import patch

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from packages.config.local_agent_config.models import CompactionConfig, MCPConfig, MCPServerConfig
from apps.runtime.local_agent_runtime.subagents import (
    ResolvedModelRoute,
    ResolvedSubagentConfiguration,
    ResolvedToolBinding,
    SkillDescriptor,
    SubagentAssetBundle,
    SubagentDefinition,
)
from apps.runtime.local_agent_runtime.task_runner import AgentExecutionRequest
from services.artifact_service.local_agent_artifact_service.store import InMemoryArtifactStore
from services.checkpoint_service.local_agent_checkpoint_service.checkpoint_models import (
    CheckpointMetadata,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.deepagent_harness import (
    LangChainDeepAgentHarness,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.interrupt_bridge import (
    ApprovalRequiredInterrupt,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.prompt_builder import PromptBuilder
from services.deepagent_runtime.local_agent_deepagent_runtime.subagent_compiler import (
    SubagentCompilationError,
    SubagentCompiler,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.mcp_provider import (
    MCPToolProvider,
    _connection_payload,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.tool_bindings import (
    SandboxToolBindings,
)
from services.memory_service.local_agent_memory_service.memory_models import MemoryRecord
from services.memory_service.local_agent_memory_service.memory_store import SQLiteMemoryStore
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    LocalExecutionSandboxFactory,
)
from services.web_service.local_agent_web_service.models import WebDocument, WebSearchResult
from langchain_core.tools import BaseTool, StructuredTool


class PromptBuilderTests(unittest.TestCase):
    def test_primary_prompt_includes_objective_and_subagent_roles(self) -> None:
        prompt = PromptBuilder().build_primary_prompt(
            identity_bundle_text="Operate carefully.",
            workspace_roots=["/workspace"],
            objective="Inspect the repository",
            constraints=["Stay inside the workspace."],
            success_criteria=["Produce a useful result."],
            available_roles=["planner", "researcher"],
        )
        self.assertIn("Operate carefully.", prompt)
        self.assertIn("Inspect the repository", prompt)
        self.assertIn("planner", prompt)
        self.assertIn("researcher", prompt)
        self.assertIn("native subagents", prompt.lower())
        self.assertIn("The governed workspace is mounted at /workspace.", prompt)
        self.assertIn("/workspace/people.csv", prompt)
        self.assertNotIn("/Users/john.eastman", prompt)

    def test_subagent_prompt_includes_role_identity_overlay_and_scope_summary(self) -> None:
        resolved = _resolved_subagent(role_id="researcher")
        prompt = PromptBuilder().build_subagent_prompt(
            resolved=resolved,
            identity_bundle_text="Primary identity",
        )
        self.assertIn("Primary identity", prompt)
        self.assertIn("Researcher identity", prompt)
        self.assertIn("Researcher overlay", prompt)
        self.assertIn("resolved_model: openai/gpt-5-mini", prompt)


class SandboxToolBindingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self._temp_dir.cleanup)
        self.workspace_root = Path(self._temp_dir.name) / "workspace"
        self.workspace_root.mkdir()
        (self.workspace_root / "README.md").write_text("hello\n", encoding="utf-8")
        self.factory = LocalExecutionSandboxFactory(
            Path(self._temp_dir.name) / "runtime",
            self.workspace_root,
        )
        self.sandbox = self.factory.for_run(
            task_id="task_1",
            run_id="run_1",
            workspace_roots=["/workspace"],
        )
        self.artifact_store = InMemoryArtifactStore(path_mapper=self.factory)
        self.memory_store = SQLiteMemoryStore(str(Path(self._temp_dir.name) / "memory.sqlite"))
        self.memory_store.write_memory(
            MemoryRecord(
                memory_id="mem_1",
                scope="project",
                namespace="docs",
                content="remember this",
                summary="memory summary",
                provenance={"source": "test"},
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
            )
        )

    def test_read_files_exposes_list_and_read_tools(self) -> None:
        bindings = SandboxToolBindings(
            sandbox=self.sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
        )
        tools = bindings.as_langchain_tools(
            (ResolvedToolBinding("read_files", ("read_file", "list_files"), True),)
        )
        tool_names = sorted(tool.name for tool in tools)
        self.assertEqual(tool_names, ["list_files", "read_file"])

    def test_memory_lookup_filters_by_allowed_scopes(self) -> None:
        bindings = SandboxToolBindings(
            sandbox=self.sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
        )
        memory_tool = next(
            tool
            for tool in bindings.as_langchain_tools(
                (ResolvedToolBinding("memory_lookup", ("memory_lookup",), False),),
                memory_scopes=("run_state",),
            )
            if tool.name == "memory_lookup"
        )
        self.assertEqual(memory_tool.invoke({"namespace": "docs"}), [])

    def test_plan_update_emits_runtime_friendly_event(self) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        bindings = SandboxToolBindings(
            sandbox=self.sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )
        payload = bindings.plan_update("Refine the task", phase="planning")
        self.assertEqual(payload["summary"], "Refine the task")
        self.assertEqual(events[0][0], "plan.updated")
        self.assertEqual(events[0][1]["phase"], "planning")

    def test_artifact_inspect_returns_metadata_and_preview(self) -> None:
        bindings = SandboxToolBindings(
            sandbox=self.sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
        )
        bindings.write_file("/workspace/artifacts/report.md", "# Report\n")
        self.artifact_store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="/workspace/artifacts/report.md",
        )
        artifacts = bindings.artifact_inspect()
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["logical_path"], "/workspace/artifacts/report.md")
        self.assertEqual(artifacts[0]["preview"], "# Report\n")

    def test_filesystem_scope_denies_workspace_access_when_only_memory_is_allowed(self) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        bindings = SandboxToolBindings(
            sandbox=self.sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )
        read_tool = next(
            tool
            for tool in bindings.as_langchain_tools(
                (ResolvedToolBinding("read_files", ("read_file", "list_files"), True),),
                filesystem_scopes=("memory",),
            )
            if tool.name == "read_file"
        )

        message = read_tool.invoke({"path": "/workspace/README.md"})
        self.assertIn("TOOL_REJECTED [scope_denied]", message)
        self.assertEqual(events[-1][0], "tool.rejected")
        self.assertEqual(events[-1][1]["code"], "scope_denied")

    def test_recoverable_path_validation_returns_tool_feedback(self) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        bindings = SandboxToolBindings(
            sandbox=self.sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        message = bindings.write_file(str(self.workspace_root / "README.md"), "updated\n")

        self.assertIn("TOOL_REJECTED [path_validation]", message)
        self.assertEqual(events[-1][0], "tool.rejected")
        self.assertEqual(events[-1][1]["code"], "path_validation")
        self.assertEqual(events[-1][1]["arguments"]["path"], "<host-native-path>")

    def test_missing_command_returns_recoverable_tool_feedback(self) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        bindings = SandboxToolBindings(
            sandbox=self.sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        message = bindings.execute_command(["atlassian"], cwd="/workspace")

        self.assertIn("TOOL_REJECTED [command_not_found]", message)
        self.assertIn("Pick an installed command", message)
        self.assertEqual(events[-1][0], "tool.rejected")
        self.assertEqual(events[-1][1]["code"], "command_not_found")
        self.assertTrue(events[-1][1]["retryable"])

    def test_web_tools_return_normalized_payloads_and_emit_events(self) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        bindings = SandboxToolBindings(
            sandbox=self.sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
            web_fetch_port=_StaticWebFetchPort(),
            web_search_port=_StaticWebSearchPort(),
        )

        tools = bindings.as_langchain_tools(
            (
                ResolvedToolBinding("web_fetch", ("web_fetch", "web.fetch", "web"), True),
                ResolvedToolBinding("web_search", ("web_search", "web.search", "web"), True),
            )
        )
        fetch_tool = next(tool for tool in tools if tool.name == "web_fetch")
        search_tool = next(tool for tool in tools if tool.name == "web_search")

        fetch_payload = fetch_tool.invoke({"url": "https://example.com"})
        search_payload = search_tool.invoke({"query": "agent runtime", "limit": 1})

        self.assertEqual(fetch_payload["final_url"], "https://example.com/final")
        self.assertEqual(search_payload[0]["source"], "duckduckgo")
        self.assertEqual([event[1]["tool"] for event in events], ["web_fetch", "web_search"])

    def test_missing_required_argument_returns_retryable_tool_feedback(self) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        bindings = SandboxToolBindings(
            sandbox=self.sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            web_search_port=_StaticWebSearchPort(),
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        tools = bindings.as_langchain_tools(
            (ResolvedToolBinding("web_search", ("web_search", "web.search", "web"), True),)
        )
        search_tool = next(tool for tool in tools if tool.name == "web_search")

        message = search_tool.invoke({"limit": 1})

        self.assertIn("TOOL_REJECTED [invalid_arguments]", message)
        self.assertIn("Field required", message)
        self.assertEqual(events[-1][0], "tool.rejected")
        self.assertEqual(events[-1][1]["tool"], "web_search")
        self.assertEqual(events[-1][1]["code"], "invalid_arguments")
        self.assertTrue(events[-1][1]["retryable"])


class MCPProviderTests(unittest.TestCase):
    def test_connection_payload_merges_env_and_env_from_host(self) -> None:
        server = MCPServerConfig(
            name="mcp-atlassian",
            transport="stdio",
            command="uvx",
            args=("mcp-atlassian",),
            env={
                "JIRA_URL": "https://company.atlassian.net",
                "JIRA_API_TOKEN": "explicit-secret",
            },
            env_from_host=("JIRA_API_TOKEN", "CONFLUENCE_API_TOKEN"),
        )

        with patch.dict(
            "os.environ",
            {
                "JIRA_API_TOKEN": "host-secret",
                "CONFLUENCE_API_TOKEN": "conf-secret",
            },
            clear=False,
        ):
            payload = _connection_payload(server)

        self.assertEqual(payload["transport"], "stdio")
        self.assertEqual(payload["command"], "uvx")
        self.assertEqual(payload["args"], ["mcp-atlassian"])
        self.assertEqual(
            payload["env"],
            {
                "JIRA_URL": "https://company.atlassian.net",
                "JIRA_API_TOKEN": "explicit-secret",
                "CONFLUENCE_API_TOKEN": "conf-secret",
            },
        )

    def test_connection_payload_preserves_remote_headers(self) -> None:
        server = MCPServerConfig(
            name="remote",
            transport="http",
            url="https://example.com/mcp",
            headers={"Authorization": "Bearer secret"},
        )

        payload = _connection_payload(server)

        self.assertEqual(
            payload,
            {
                "transport": "http",
                "url": "https://example.com/mcp",
                "headers": {"Authorization": "Bearer secret"},
            },
        )


class SubagentCompilerTests(unittest.TestCase):
    def test_compiler_builds_subagent_with_prompt_model_tools_and_skills(self) -> None:
        captures: list[tuple[str, str]] = []
        compiler = SubagentCompiler(
            prompt_builder=PromptBuilder(),
            model_factory=_recording_model_factory(captures),
        )
        temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(temp_dir.cleanup)
        workspace_root = Path(temp_dir.name) / "workspace"
        workspace_root.mkdir()
        factory = LocalExecutionSandboxFactory(
            Path(temp_dir.name) / "runtime",
            workspace_root,
        )
        sandbox = factory.for_run(
            task_id="task_1",
            run_id="run_1",
            workspace_roots=["/workspace"],
        )
        bindings = SandboxToolBindings(
            sandbox=sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=InMemoryArtifactStore(path_mapper=factory),
        )
        skill_path = Path(temp_dir.name) / "skill.md"
        skill_path.write_text("# Skill\nFollow the skill.\n", encoding="utf-8")
        resolved = _resolved_subagent(role_id="researcher", skill_path=skill_path)

        compiled = compiler.compile_subagents(
            resolved_subagents=[resolved],
            identity_bundle_text="Primary identity",
            delegation_description="Inspect the repository",
            run_id="run_1",
            tool_bindings=bindings,
        )

        self.assertEqual(len(compiled), 1)
        self.assertEqual(compiled[0]["name"], "Researcher")
        self.assertIn("Researcher identity", compiled[0]["system_prompt"])
        self.assertEqual(captures, [("gpt-5-mini", "openai")])
        self.assertEqual(_tool_names(compiled[0]["tools"]), ["list_files", "read_file"])
        self.assertEqual(compiled[0]["skills"], ["# Skill\nFollow the skill."])

    def test_compiler_preserves_multi_role_model_tool_and_skill_isolation(self) -> None:
        captures: list[tuple[str, str]] = []
        compiler = SubagentCompiler(
            prompt_builder=PromptBuilder(),
            model_factory=_recording_model_factory(captures),
        )
        temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(temp_dir.cleanup)
        workspace_root = Path(temp_dir.name) / "workspace"
        workspace_root.mkdir()
        factory = LocalExecutionSandboxFactory(
            Path(temp_dir.name) / "runtime",
            workspace_root,
        )
        sandbox = factory.for_run(
            task_id="task_1",
            run_id="run_1",
            workspace_roots=["/workspace"],
        )
        bindings = SandboxToolBindings(
            sandbox=sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=InMemoryArtifactStore(path_mapper=factory),
        )
        researcher_skill = Path(temp_dir.name) / "researcher-skill.md"
        researcher_skill.write_text("# Research\n", encoding="utf-8")
        coder_skill = Path(temp_dir.name) / "coder-skill.md"
        coder_skill.write_text("# Code\n", encoding="utf-8")

        compiled = compiler.compile_subagents(
            resolved_subagents=[
                _resolved_subagent(role_id="researcher", skill_path=researcher_skill),
                _resolved_subagent_with_options(
                    role_id="coder",
                    skill_path=coder_skill,
                    tool_scope=("read_files", "write_files", "execute_commands"),
                    model_name="gpt-5-coder",
                ),
            ],
            identity_bundle_text="Primary identity",
            delegation_description="Inspect the repository",
            run_id="run_1",
            tool_bindings=bindings,
        )

        self.assertEqual(len(compiled), 2)
        self.assertEqual(captures, [("gpt-5-mini", "openai"), ("gpt-5-coder", "openai")])
        self.assertEqual(_tool_names(compiled[0]["tools"]), ["list_files", "read_file"])
        self.assertEqual(
            _tool_names(compiled[1]["tools"]),
            ["execute_command", "list_files", "read_file", "write_file"],
        )
        self.assertEqual(compiled[0]["skills"], ["# Research"])
        self.assertEqual(compiled[1]["skills"], ["# Code"])

    def test_compiler_fails_when_skill_cannot_be_read(self) -> None:
        compiler = SubagentCompiler(
            prompt_builder=PromptBuilder(),
            model_factory=lambda *args, **kwargs: {},
        )
        temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(temp_dir.cleanup)
        workspace_root = Path(temp_dir.name) / "workspace"
        workspace_root.mkdir()
        factory = LocalExecutionSandboxFactory(
            Path(temp_dir.name) / "runtime",
            workspace_root,
        )
        sandbox = factory.for_run(
            task_id="task_1",
            run_id="run_1",
            workspace_roots=["/workspace"],
        )
        bindings = SandboxToolBindings(
            sandbox=sandbox,
            task_id="task_1",
            run_id="run_1",
            artifact_store=InMemoryArtifactStore(path_mapper=factory),
        )

        with self.assertRaises(SubagentCompilationError):
            compiler.compile_subagents(
                resolved_subagents=[
                    _resolved_subagent(
                        role_id="researcher",
                        skill_path=Path(temp_dir.name) / "missing-skill.md",
                    )
                ],
                identity_bundle_text="Primary identity",
                delegation_description="Inspect the repository",
                run_id="run_1",
                tool_bindings=bindings,
            )


class LangChainDeepAgentHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self._temp_dir.cleanup)
        self.workspace_root = Path(self._temp_dir.name) / "workspace"
        self.workspace_root.mkdir()
        (self.workspace_root / "README.md").write_text("# Demo\n", encoding="utf-8")
        self.factory = LocalExecutionSandboxFactory(
            Path(self._temp_dir.name) / "runtime",
            self.workspace_root,
        )
        self.sandbox = self.factory.for_run(
            task_id="task_1",
            run_id="run_1",
            workspace_roots=["/workspace"],
        )
        self.artifact_store = InMemoryArtifactStore(path_mapper=self.factory)
        self.memory_store = SQLiteMemoryStore(str(Path(self._temp_dir.name) / "memory.sqlite"))

    def test_harness_creates_primary_agent_with_compiled_subagents(self) -> None:
        events: list[tuple[str, dict[str, object]]] = []
        captures: dict[str, Any] = {}
        skill_path = Path(self._temp_dir.name) / "skill.md"
        skill_path.write_text("# Skill\nUse it.\n", encoding="utf-8")
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[_resolved_subagent(role_id="researcher", skill_path=skill_path)],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
            primary_skills=(
                SkillDescriptor(
                    skill_id="runtime-governance",
                    name="Runtime governance",
                    prompt_path=skill_path,
                    source="file",
                    prompt_text="# Skill\nUse it.",
                ),
            ),
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=_capture_model_factory(captures),
            agent_factory=lambda **kwargs: FakeCompiledAgent(kwargs, captures),
        ).execute(
            request,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        self.assertTrue(result.success)
        self.assertEqual(
            result.output_artifacts,
            [
                "/workspace/artifacts/result.md",
                "/workspace/artifacts/task_1/run_1/final_response.md",
            ],
        )
        self.assertEqual(captures["agent_kwargs"]["name"], "primary")
        self.assertEqual(captures["agent_kwargs"]["skills"], ["# Skill\nUse it."])
        self.assertIn("skill-installer", _tool_names(captures["agent_kwargs"]["tools"]))
        self.assertEqual(captures["agent_kwargs"]["subagents"][0]["name"], "Researcher")
        self.assertNotIn("repo_summary.md", captures["invoke_payload"]["messages"][0]["content"])
        self.assertEqual(
            self.sandbox.read_text("/workspace/artifacts/task_1/run_1/final_response.md"),
            "Delegated execution started and completed successfully.\n",
        )
        self.assertIn("subagent.started", [event_type for event_type, _ in events])
        self.assertIn("subagent.completed", [event_type for event_type, _ in events])
        self.assertTrue(
            any(
                payload.get("subagentId") == "researcher"
                and payload.get("taskDescription")
                == "Delegated researcher work for objective: Inspect the repository"
                and payload.get("runId") == "run_1"
                for event_type, payload in events
                if event_type == "subagent.started"
            )
        )
        self.assertTrue(
            any(
                payload.get("subagentId") == "researcher"
                and payload.get("status") == "success"
                and isinstance(payload.get("duration"), float)
                for event_type, payload in events
                if event_type == "subagent.completed"
            )
        )

    def test_harness_emits_failed_completion_when_subagent_raises(self) -> None:
        events: list[tuple[str, dict[str, object]]] = []
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[_resolved_subagent(role_id="researcher")],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, *, model_provider: {
                "model_name": model_name,
                "model_provider": model_provider,
            },
            agent_factory=lambda **kwargs: FailingCompiledAgent(kwargs, {}),
        ).execute(
            request,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "delegated failure")
        started_events = [
            payload for event_type, payload in events if event_type == "subagent.started"
        ]
        completed_events = [
            payload for event_type, payload in events if event_type == "subagent.completed"
        ]
        self.assertEqual(len(started_events), 1)
        self.assertEqual(len(completed_events), 1)
        self.assertEqual(
            started_events[0]["taskDescription"],
            "Delegated researcher work for objective: Inspect the repository",
        )
        self.assertEqual(completed_events[0]["status"], "failed")
        self.assertEqual(completed_events[0]["subagentId"], "researcher")

    def test_harness_captures_final_response_artifact_for_failed_result_payload(self) -> None:
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: FailingResultAgent(kwargs, {}),
        ).execute(request, on_event=lambda *_: None)

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "model reported failure")
        self.assertEqual(
            result.output_artifacts,
            ["/workspace/artifacts/task_1/run_1/final_response.md"],
        )
        self.assertEqual(
            self.sandbox.read_text("/workspace/artifacts/task_1/run_1/final_response.md"),
            "Model produced a final response before failing.\n",
        )

    def test_harness_pauses_cleanly_when_runtime_requests_approval(self) -> None:
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
            checkpoint_controller=FakeCheckpointController(),
            governed_operation=lambda context: (
                None
                if context.operation_type != "file.write"
                else (_ for _ in ()).throw(
                    ApprovalRequiredInterrupt(
                        approval_id="approval_1",
                        summary="Allow writes to /docs/** for this run",
                    )
                )
            ),
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: FakeCompiledAgent(kwargs, {}),
        ).execute(request, on_event=lambda *_: None)

        self.assertTrue(result.paused)
        self.assertTrue(result.awaiting_approval)
        self.assertEqual(result.pending_approval_id, "approval_1")
        self.assertEqual(result.pause_reason, "awaiting approval")

    def test_harness_passes_checkpoint_context_without_leaking_framework_types(self) -> None:
        events: list[tuple[str, dict[str, object]]] = []
        captures: dict[str, Any] = {}
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
            checkpoint_controller=FakeCheckpointController(),
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, *, model_provider: captures.setdefault(
                "model",
                {"model_name": model_name, "model_provider": model_provider},
            ),
            agent_factory=lambda **kwargs: FakeCompiledAgent(kwargs, captures),
        ).execute(
            request,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        self.assertTrue(result.success)
        self.assertEqual(captures["agent_kwargs"]["checkpointer"], "checkpointer")
        self.assertEqual(
            captures["invoke_config"],
            {"configurable": {"thread_id": "thread_1"}},
        )
        checkpoint_events = [
            payload for event_type, payload in events if event_type == "checkpoint.saved"
        ]
        self.assertEqual(len(checkpoint_events), 2)
        self.assertEqual(checkpoint_events[0]["checkpoint_id"], "ckpt_1")
        self.assertEqual(checkpoint_events[1]["checkpoint_id"], "ckpt_2")

    def test_harness_uses_persisted_conversation_messages_when_provided(self) -> None:
        captures: dict[str, Any] = {}
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
            conversation_messages=(
                {"role": "user", "content": "Inspect the repository"},
                {"role": "assistant", "content": "Which area should I inspect?"},
                {"role": "user", "content": "Focus on docs only."},
            ),
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: FakeCompiledAgent(kwargs, captures),
        ).execute(request, on_event=lambda *_: None)

        self.assertTrue(result.success)
        self.assertEqual(
            captures["invoke_payload"]["messages"],
            [
                {"role": "user", "content": "Inspect the repository"},
                {"role": "assistant", "content": "Which area should I inspect?"},
                {"role": "user", "content": "Focus on docs only."},
            ],
        )

    def test_harness_passes_compaction_middleware_into_agent_factory(self) -> None:
        captures: dict[str, Any] = {}
        class _FakeStrategy:
            def build_middleware(self, *, model, policy, on_compaction):
                return ["mw_1", "mw_2"]

        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            compaction_policy=CompactionConfig(),
            compaction_strategy=_FakeStrategy(),
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: FakeCompiledAgent(kwargs, captures),
        ).execute(request, on_event=lambda *_: None)

        self.assertTrue(result.success)
        middleware = captures["agent_kwargs"]["middleware"]
        self.assertGreaterEqual(len(middleware), 2)

    def test_harness_pauses_for_request_user_input_tool(self) -> None:
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
            checkpoint_controller=FakeCheckpointController(),
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: ClarificationAgent(kwargs, {}),
        ).execute(request, on_event=lambda *_: None)

        self.assertTrue(result.paused)
        self.assertEqual(result.pause_reason, "awaiting_user_input")
        self.assertEqual(result.requested_user_input, "Which area should I inspect?")

    def test_harness_skips_final_response_artifact_for_empty_or_missing_content(self) -> None:
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: EmptyAssistantAgent(kwargs, {}),
        ).execute(request, on_event=lambda *_: None)

        self.assertTrue(result.success)
        self.assertEqual(result.output_artifacts, [])
        self.assertFalse(self.sandbox.exists("/workspace/artifacts/task_1/run_1/final_response.md"))

    def test_harness_writes_run_specific_final_response_paths(self) -> None:
        harness = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: FakeCompiledAgent(kwargs, {}),
        )
        first_request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )
        second_sandbox = self.factory.for_run(
            task_id="task_1",
            run_id="run_2",
            workspace_roots=["/workspace"],
        )
        second_request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_2",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=second_sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )

        first_result = harness.execute(first_request, on_event=lambda *_: None)
        second_result = harness.execute(second_request, on_event=lambda *_: None)

        self.assertIn(
            "/workspace/artifacts/task_1/run_1/final_response.md", first_result.output_artifacts
        )
        self.assertIn(
            "/workspace/artifacts/task_1/run_2/final_response.md", second_result.output_artifacts
        )
        self.assertTrue(self.sandbox.exists("/workspace/artifacts/task_1/run_1/final_response.md"))
        self.assertTrue(
            second_sandbox.exists("/workspace/artifacts/task_1/run_2/final_response.md")
        )

    def test_harness_captures_block_based_assistant_content(self) -> None:
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: BlockAssistantAgent(kwargs, {}),
        ).execute(request, on_event=lambda *_: None)

        self.assertTrue(result.success)
        self.assertIn(
            "/workspace/artifacts/task_1/run_1/final_response.md", result.output_artifacts
        )
        self.assertEqual(
            self.sandbox.read_text("/workspace/artifacts/task_1/run_1/final_response.md"),
            "First block\nSecond block\n",
        )

    def test_harness_captures_langchain_ai_message_content(self) -> None:
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: AIMessageAgent(kwargs, {}),
        ).execute(request, on_event=lambda *_: None)

        self.assertTrue(result.success)
        self.assertIn(
            "/workspace/artifacts/task_1/run_1/final_response.md", result.output_artifacts
        )
        self.assertEqual(
            self.sandbox.read_text("/workspace/artifacts/task_1/run_1/final_response.md"),
            "AIMessage response body\n",
        )

    def test_harness_loads_mcp_tools_for_primary_and_opted_in_subagents(self) -> None:
        captures: dict[str, Any] = {}
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[
                _resolved_subagent_with_options(
                    role_id="researcher",
                    skill_path=None,
                    tool_scope=("read_files", "mcp_tools"),
                    model_name="gpt-5-mini",
                ),
                _resolved_subagent_with_options(
                    role_id="coder",
                    skill_path=None,
                    tool_scope=("read_files",),
                    model_name="gpt-5-coder",
                ),
            ],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            mcp_config=_fixture_mcp_config(),
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: FakeCompiledAgent(kwargs, captures),
        ).execute(request, on_event=lambda *_: None)

        self.assertTrue(result.success)
        self.assertIn("fixture_echo_text", _tool_names(captures["agent_kwargs"]["tools"]))
        researcher = next(
            subagent
            for subagent in captures["agent_kwargs"]["subagents"]
            if subagent["name"] == "Researcher"
        )
        coder = next(
            subagent
            for subagent in captures["agent_kwargs"]["subagents"]
            if subagent["name"] == "Coder"
        )
        self.assertIn("fixture_echo_text", _tool_names(researcher["tools"]))
        self.assertNotIn("fixture_echo_text", _tool_names(coder["tools"]))

    def test_harness_suppresses_mcp_tools_when_capability_not_allowed(self) -> None:
        captures: dict[str, Any] = {}
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[
                _resolved_subagent_with_options(
                    role_id="researcher",
                    skill_path=None,
                    tool_scope=("read_files", "mcp_tools"),
                    model_name="gpt-5-mini",
                )
            ],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=["read_file", "list_files", "write_file"],
            metadata={},
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            mcp_config=_fixture_mcp_config(),
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: FakeCompiledAgent(kwargs, captures),
        ).execute(request, on_event=lambda *_: None)

        self.assertTrue(result.success)
        self.assertNotIn("fixture_echo_text", _tool_names(captures["agent_kwargs"]["tools"]))
        researcher = captures["agent_kwargs"]["subagents"][0]
        self.assertNotIn("fixture_echo_text", _tool_names(researcher["tools"]))

    def test_harness_pauses_for_imported_project_stdio_mcp_server(self) -> None:
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Use MCP tools",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
            governed_operation=lambda context: (
                None
                if context.operation_type != "mcp.server.connect"
                else (_ for _ in ()).throw(
                    ApprovalRequiredInterrupt(
                        approval_id="approval_mcp_1",
                        summary="Allow MCP stdio server fixture for this run",
                    )
                )
            ),
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            mcp_config=_fixture_mcp_config(source="project_root_mcp_json"),
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: MCPPrimaryAgent(kwargs, {}),
        ).execute(request, on_event=lambda *_: None)

        self.assertTrue(result.paused)
        self.assertTrue(result.awaiting_approval)
        self.assertEqual(result.pause_reason, "awaiting approval")

    def test_harness_emits_mcp_tool_called_event_metadata(self) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Use MCP tools",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
            governed_operation=lambda context: None,
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            mcp_config=_fixture_mcp_config(),
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: MCPPrimaryAgent(kwargs, {}),
        ).execute(
            request,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        self.assertTrue(result.success)
        self.assertEqual(
            self.sandbox.read_text("/workspace/artifacts/task_1/run_1/final_response.md"),
            "fixture:primary-call\n",
        )
        tool_event = next(
            payload
            for event_type, payload in events
            if event_type == "tool.called" and payload.get("tool_source") == "mcp"
        )
        self.assertEqual(tool_event["server_name"], "fixture")
        self.assertEqual(tool_event["transport"], "stdio")
        self.assertEqual(tool_event["raw_tool_name"], "echo_text")
        self.assertEqual(tool_event["exposed_tool_name"], "fixture_echo_text")

    def test_harness_keeps_running_after_missing_command_tool_rejection(self) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: MissingCommandAgent(kwargs, {}),
        ).execute(
            request,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        self.assertTrue(result.success)
        self.assertEqual(
            self.sandbox.read_text("/workspace/artifacts/task_1/run_1/final_response.md"),
            "TOOL_REJECTED [command_not_found]: Command 'atlassian' is not installed or not on PATH. Pick an installed command or verify the executable name before retrying.\n",
        )
        rejection_event = next(payload for event_type, payload in events if event_type == "tool.rejected")
        self.assertEqual(rejection_event["tool"], "execute_command")
        self.assertEqual(rejection_event["code"], "command_not_found")
        self.assertTrue(rejection_event["retryable"])

    def test_harness_keeps_running_after_invalid_mcp_tool_arguments(self) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Use MCP tools",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )

        async def _fake_load_mcp_tools(*args: Any, **kwargs: Any) -> list[BaseTool]:
            return [_invalid_mcp_search_tool()]

        with patch(
            "services.deepagent_runtime.local_agent_deepagent_runtime.mcp_provider.load_mcp_tools",
            _fake_load_mcp_tools,
        ):
            result = LangChainDeepAgentHarness(
                model_name="gpt-5",
                model_provider="openai",
                mcp_config=_fixture_mcp_config(),
                model_factory=lambda model_name, *, model_provider: {},
                agent_factory=lambda **kwargs: InvalidMCPArgumentsAgent(kwargs, {}),
            ).execute(
                request,
                on_event=lambda event_type, payload: events.append((event_type, payload)),
            )

        self.assertTrue(result.success)
        artifact_text = self.sandbox.read_text("/workspace/artifacts/task_1/run_1/final_response.md")
        self.assertIn("TOOL_REJECTED [invalid_arguments]", artifact_text)
        self.assertIn("Input should be less than or equal to 50", artifact_text)
        self.assertIn("Adjust the tool arguments to satisfy the schema", artifact_text)
        rejection_event = next(payload for event_type, payload in events if event_type == "tool.rejected")
        self.assertEqual(rejection_event["tool"], "fixture_search")
        self.assertEqual(rejection_event["code"], "invalid_arguments")
        self.assertTrue(rejection_event["retryable"])

    def test_harness_keeps_running_after_missing_local_tool_argument(self) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Search the web",
            workspace_roots=["/workspace"],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            resolved_subagents=[],
            artifact_store=self.artifact_store,
            memory_store=self.memory_store,
            allowed_capabilities=[],
            metadata={},
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            web_search_port=_StaticWebSearchPort(),
            model_factory=lambda model_name, *, model_provider: {},
            agent_factory=lambda **kwargs: MissingLocalToolArgumentAgent(kwargs, {}),
        ).execute(
            request,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        self.assertTrue(result.success)
        artifact_text = self.sandbox.read_text("/workspace/artifacts/task_1/run_1/final_response.md")
        self.assertIn("TOOL_REJECTED [invalid_arguments]", artifact_text)
        self.assertIn("Field required", artifact_text)
        rejection_event = next(payload for event_type, payload in events if event_type == "tool.rejected")
        self.assertEqual(rejection_event["tool"], "web_search")
        self.assertEqual(rejection_event["code"], "invalid_arguments")
        self.assertTrue(rejection_event["retryable"])


class MCPToolProviderTests(unittest.TestCase):
    def test_invalid_tool_arguments_return_retryable_rejection(self) -> None:
        events: list[tuple[str, dict[str, Any]]] = []
        provider = MCPToolProvider(
            config=_fixture_mcp_config(),
            task_id="task_1",
            run_id="run_1",
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        tool = provider._wrap_tool(
            role="primary",
            server=_fixture_mcp_config().servers["fixture"],
            raw_tool=_invalid_mcp_search_tool(),
        )

        message = tool.invoke({"query": "agent runtime", "limit": 100})

        self.assertIn("TOOL_REJECTED [invalid_arguments]", message)
        self.assertIn("Adjust the tool arguments to satisfy the schema", message)
        self.assertEqual(events[-1][0], "tool.rejected")
        self.assertEqual(events[-1][1]["tool"], "fixture_search")
        self.assertEqual(events[-1][1]["code"], "invalid_arguments")
        self.assertTrue(events[-1][1]["retryable"])


class FakeCompiledAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._tools = cast(list[BaseTool], kwargs["tools"])
        self._subagents = kwargs.get("subagents") or []
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_config"] = config
        self._captures["invoke_payload"] = input
        for subagent in self._subagents:
            for middleware in subagent.get("middleware", []):
                middleware.wrap_model_call(FakeModelRequest(), lambda request: {"ok": True})
        self._invoke_tool("list_files", {"root": "/workspace"})
        self._invoke_tool("read_file", {"path": "/workspace/README.md"})
        self._invoke_tool(
            "write_file",
            {
                "path": "/workspace/artifacts/result.md",
                "content": "# Result\nDeep Agent execution complete.\n",
            },
        )
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": "Delegated execution started and completed successfully.",
                }
            ]
        }

    def _invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        tool = next(tool for tool in self._tools if tool.name == tool_name)
        return tool.invoke(arguments)


class FailingCompiledAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._subagents = kwargs.get("subagents") or []
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_config"] = config
        self._captures["invoke_payload"] = input
        for subagent in self._subagents:
            for middleware in subagent.get("middleware", []):
                middleware.wrap_model_call(
                    FakeModelRequest(),
                    lambda request: (_ for _ in ()).throw(RuntimeError("delegated failure")),
                )
        raise AssertionError("expected delegated failure before agent completion")


class FailingResultAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_config"] = config
        self._captures["invoke_payload"] = input
        return {
            "success": False,
            "error": "model reported failure",
            "messages": [
                {
                    "role": "assistant",
                    "content": "Model produced a final response before failing.",
                }
            ],
        }


class ClarificationAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._tools = cast(list[BaseTool], kwargs["tools"])
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_config"] = config
        self._captures["invoke_payload"] = input
        tool = next(tool for tool in self._tools if tool.name == "request_user_input")
        tool.invoke({"question": "Which area should I inspect?"})
        raise AssertionError("request_user_input should interrupt execution")


class EmptyAssistantAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_config"] = config
        self._captures["invoke_payload"] = input
        return {"messages": [{"role": "assistant", "content": "   "}]}


class BlockAssistantAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_config"] = config
        self._captures["invoke_payload"] = input
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "First block"},
                        {"type": "reasoning", "thinking": "ignore"},
                        {"type": "output_text", "text": "Second block"},
                    ],
                }
            ]
        }


class AIMessageAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_config"] = config
        self._captures["invoke_payload"] = input
        return {"messages": [AIMessage(content="AIMessage response body")]}


class MCPPrimaryAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._tools = cast(list[BaseTool], kwargs["tools"])
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_config"] = config
        self._captures["invoke_payload"] = input
        tool = next(tool for tool in self._tools if tool.name == "fixture_echo_text")
        text = _tool_result_text(tool.invoke({"text": "primary-call"}))
        return {"messages": [{"role": "assistant", "content": text}]}


class MissingCommandAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._tools = cast(list[BaseTool], kwargs["tools"])
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_config"] = config
        self._captures["invoke_payload"] = input
        execute_tool = next(tool for tool in self._tools if tool.name == "execute_command")
        write_tool = next(tool for tool in self._tools if tool.name == "write_file")
        message = execute_tool.invoke({"command": ["atlassian"], "cwd": "/workspace"})
        write_tool.invoke(
            {
                "path": "/workspace/artifacts/task_1/run_1/final_response.md",
                "content": f"{message}\n",
            }
        )
        return {"messages": [{"role": "assistant", "content": str(message)}]}


class InvalidMCPArgumentsAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._tools = cast(list[BaseTool], kwargs["tools"])
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_config"] = config
        self._captures["invoke_payload"] = input
        search_tool = next(tool for tool in self._tools if tool.name == "fixture_search")
        write_tool = next(tool for tool in self._tools if tool.name == "write_file")
        message = search_tool.invoke({"query": "agent runtime", "limit": 100})
        write_tool.invoke(
            {
                "path": "/workspace/artifacts/task_1/run_1/final_response.md",
                "content": f"{message}\n",
            }
        )
        return {"messages": [{"role": "assistant", "content": str(message)}]}


class MissingLocalToolArgumentAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._tools = cast(list[BaseTool], kwargs["tools"])
        self._captures = captures
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self._captures["invoke_config"] = config
        self._captures["invoke_payload"] = input
        search_tool = next(tool for tool in self._tools if tool.name == "web_search")
        write_tool = next(tool for tool in self._tools if tool.name == "write_file")
        message = search_tool.invoke({"limit": 1})
        write_tool.invoke(
            {
                "path": "/workspace/artifacts/task_1/run_1/final_response.md",
                "content": f"{message}\n",
            }
        )
        return {"messages": [{"role": "assistant", "content": str(message)}]}


class FakeCheckpointController:
    def __init__(self) -> None:
        self._index = 0
        self.thread_id = "thread_1"
        self.latest_checkpoint_id = "ckpt_0"
        self.is_resumed = False

    def record_checkpoint(self, reason: str | None = None) -> CheckpointMetadata:
        self._index += 1
        checkpoint_id = f"ckpt_{self._index}"
        self.latest_checkpoint_id = checkpoint_id
        return CheckpointMetadata(
            checkpoint_id=checkpoint_id,
            task_id="task_1",
            run_id="run_1",
            thread_id=self.thread_id,
            checkpoint_index=self._index,
            created_at=f"2025-01-01T00:00:0{self._index}Z",
            reason=reason,
        )

    def build_agent_kwargs(self) -> dict[str, Any]:
        return {"checkpointer": "checkpointer"}

    def build_invoke_config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id}}


class FakeModelRequest:
    system_message = None


def _capture_model_factory(captures: dict[str, Any]):
    def _factory(model_name: str, *, model_provider: str) -> dict[str, Any]:
        captures.setdefault("models", []).append(
            {"model_name": model_name, "model_provider": model_provider}
        )
        return {"model_name": model_name, "model_provider": model_provider}

    return _factory


def _recording_model_factory(captures: list[tuple[str, str]]):
    def _factory(model_name: str, *, model_provider: str) -> dict[str, Any]:
        captures.append((model_name, model_provider))
        return {"model_name": model_name, "model_provider": model_provider}

    return _factory


def _tool_names(tools: object) -> list[str]:
    typed_tools = cast(list[BaseTool], tools)
    return sorted(tool.name for tool in typed_tools)


def _resolved_subagent(
    role_id: str, skill_path: Path | None = None
) -> ResolvedSubagentConfiguration:
    return _resolved_subagent_with_options(
        role_id=role_id,
        skill_path=skill_path,
        tool_scope=("read_files",),
        model_name="gpt-5-mini",
    )


def _resolved_subagent_with_options(
    *,
    role_id: str,
    skill_path: Path | None,
    tool_scope: tuple[str, ...],
    model_name: str,
) -> ResolvedSubagentConfiguration:
    identity_path = Path(f"/tmp/{role_id}/IDENTITY.md")
    system_prompt_path = Path(f"/tmp/{role_id}/SYSTEM_PROMPT.md")
    definition = SubagentDefinition(
        role_id=role_id,
        name=role_id.title(),
        description=f"{role_id.title()} role",
        model_profile=role_id,
        tool_scope=tool_scope,
        memory_scope=("project", "run"),
        filesystem_scope=("/",),
        identity_path=identity_path,
        system_prompt_path=system_prompt_path,
        skills_path=skill_path.parent if skill_path is not None else None,
    )
    return ResolvedSubagentConfiguration(
        asset_bundle=SubagentAssetBundle(
            definition=definition,
            identity_text=f"{role_id.title()} identity",
            system_prompt_text=f"{role_id.title()} overlay",
        ),
        model_route=ResolvedModelRoute(
            provider="openai",
            model=model_name,
            profile_name=role_id,
            source="subagent_override",
        ),
        tool_bindings=tuple(_resolved_tool_binding(tool_id) for tool_id in tool_scope),
        skills=(
            ()
            if skill_path is None
            else (
                SkillDescriptor(
                    skill_id=f"{role_id}-skill",
                    name=f"{role_id.title()} skill",
                    prompt_path=skill_path,
                    source="file",
                    prompt_text=(
                        skill_path.read_text(encoding="utf-8").strip()
                        if skill_path.is_file()
                        else ""
                    ),
                ),
            )
        ),
    )


def _resolved_tool_binding(tool_id: str) -> ResolvedToolBinding:
    aliases = {
        "read_files": ("read_file", "list_files", "filesystem"),
        "write_files": ("write_file", "filesystem"),
        "execute_commands": ("execute_command", "commands"),
        "memory_lookup": ("memory_lookup", "/.memory"),
        "plan_update": ("plan_update", "planning"),
        "artifact_inspect": ("artifact_inspect", "artifacts"),
        "mcp_tools": ("mcp_tools", "mcp", "mcp.tools"),
        "web_fetch": ("web_fetch", "web.fetch", "web"),
        "web_search": ("web_search", "web.search", "web"),
    }[tool_id]
    return ResolvedToolBinding(
        tool_id=tool_id,
        capability_aliases=aliases,
        requires_policy=tool_id
        in {
            "read_files",
            "write_files",
            "execute_commands",
            "web_fetch",
            "web_search",
            "mcp_tools",
        },
    )


def _fixture_mcp_config(source: str = "runtime_toml") -> MCPConfig:
    return MCPConfig(
        tool_name_prefix=True,
        servers={
            "fixture": MCPServerConfig(
                name="fixture",
                transport="stdio",
                command=sys.executable,
                args=(str(Path("tests/fixtures/mcp_echo_server.py").resolve()),),
                source=source,
                source_path=str(Path("tests/fixtures/mcp_echo_server.py").resolve()),
            )
        },
    )


class _InvalidSearchArgs(BaseModel):
    query: str
    limit: int = Field(default=5, le=50)


def _invalid_mcp_search_tool() -> BaseTool:
    return StructuredTool.from_function(
        func=lambda query, limit=5: [{"text": f"{query}:{limit}"}],
        name="fixture_search",
        description="Search fixture MCP tool.",
        args_schema=_InvalidSearchArgs,
    )


def _tool_result_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        if parts:
            return "\n".join(parts)
    return str(value)


class _StaticWebFetchPort:
    def fetch(self, url: str, **_: Any) -> WebDocument:
        return WebDocument(
            url=url,
            final_url=f"{url}/final",
            title="Example",
            markdown_content="# Example\n\nCaptured.",
            fetched_at="2025-01-01T00:00:00Z",
            content_type="text/html",
            status_code=200,
        )


class _StaticWebSearchPort:
    def search(
        self, query: str, *, limit: int = 5, locale: str | None = None
    ) -> list[WebSearchResult]:
        return [
            WebSearchResult(
                title=f"Result for {query}",
                url="https://example.com/result",
                snippet=f"limit={limit} locale={locale}",
                rank=1,
                source="duckduckgo",
            )
        ]


if __name__ == "__main__":
    unittest.main()
