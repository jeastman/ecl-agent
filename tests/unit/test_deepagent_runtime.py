from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from apps.runtime.local_agent_runtime.task_runner import AgentExecutionRequest
from services.deepagent_runtime.local_agent_deepagent_runtime.deepagent_harness import (
    LangChainDeepAgentHarness,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.prompt_builder import PromptBuilder
from services.deepagent_runtime.local_agent_deepagent_runtime.tool_bindings import (
    SandboxToolBindings,
)
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    LocalExecutionSandboxFactory,
)


class PromptBuilderTests(unittest.TestCase):
    def test_prompt_builder_includes_identity_boundaries_and_artifact_target(self) -> None:
        prompt = PromptBuilder().build_system_prompt(
            identity_bundle_text="Operate carefully.",
            workspace_roots=["/tmp/workspace"],
            objective="Inspect the repository",
            constraints=["Stay inside the workspace."],
            success_criteria=["Produce the summary artifact."],
        )
        self.assertIn("Operate carefully.", prompt)
        self.assertIn("Inspect the repository", prompt)
        self.assertIn("/tmp/workspace", prompt)
        self.assertIn("artifacts/repo_summary.md", prompt)


class SandboxToolBindingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self._temp_dir.cleanup)
        self.workspace_root = Path(self._temp_dir.name) / "workspace"
        self.workspace_root.mkdir()
        (self.workspace_root / "README.md").write_text("hello\n", encoding="utf-8")
        self.factory = LocalExecutionSandboxFactory(Path(self._temp_dir.name) / "runtime")
        self.sandbox = self.factory.for_run(
            task_id="task_1",
            run_id="run_1",
            workspace_roots=[str(self.workspace_root)],
        )

    def test_tool_bindings_emit_events_and_delegate(self) -> None:
        events: list[tuple[str, dict[str, object]]] = []
        bindings = SandboxToolBindings(
            sandbox=self.sandbox,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )
        files = bindings.list_files("workspace")
        content = bindings.read_file("workspace/README.md")
        written_path = bindings.write_file("scratch/output.md", "# generated\n")
        command_result = bindings.execute_command(
            [sys.executable, "-c", "print('ok')"],
            cwd="workspace",
        )

        self.assertIn("workspace/README.md", files)
        self.assertEqual(content, "hello\n")
        self.assertEqual(written_path, "scratch/output.md")
        self.assertEqual(command_result["exit_code"], 0)
        self.assertEqual([event_type for event_type, _ in events], [
            "tool.called",
            "tool.called",
            "tool.called",
            "tool.called",
        ])
        self.assertEqual([payload["tool"] for _, payload in events], [
            "list_files",
            "read_file",
            "write_file",
            "execute_command",
        ])


class LangChainDeepAgentHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self._temp_dir.cleanup)
        self.workspace_root = Path(self._temp_dir.name) / "workspace"
        self.workspace_root.mkdir()
        (self.workspace_root / "README.md").write_text("# Demo\n", encoding="utf-8")
        (self.workspace_root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
        self.factory = LocalExecutionSandboxFactory(Path(self._temp_dir.name) / "runtime")
        self.sandbox = self.factory.for_run(
            task_id="task_1",
            run_id="run_1",
            workspace_roots=[str(self.workspace_root)],
        )

    def test_harness_generates_reference_artifact_and_emits_runtime_friendly_events(self) -> None:
        events: list[tuple[str, dict[str, object]]] = []
        captures: dict[str, Any] = {}
        request = AgentExecutionRequest(
            task_id="task_1",
            run_id="run_1",
            objective="Inspect the repository",
            workspace_roots=[str(self.workspace_root)],
            identity_bundle_text="Operate carefully.",
            sandbox=self.sandbox,
            allowed_capabilities=[],
            metadata={},
        )

        result = LangChainDeepAgentHarness(
            model_name="gpt-5",
            model_provider="openai",
            model_factory=lambda model_name, model_provider: captures.setdefault(
                "model",
                {"model_name": model_name, "model_provider": model_provider},
            ),
            agent_factory=lambda **kwargs: FakeCompiledAgent(kwargs, captures),
        ).execute(
            request,
            on_event=lambda event_type, payload: events.append((event_type, payload)),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.output_artifacts, ["workspace/artifacts/repo_summary.md"])
        self.assertEqual(captures["model"]["model_name"], "gpt-5")
        self.assertEqual(captures["model"]["model_provider"], "openai")
        self.assertEqual(captures["agent_kwargs"]["name"], "primary")
        self.assertIn("artifacts/repo_summary.md", captures["agent_kwargs"]["system_prompt"])
        artifact_path = self.workspace_root / "artifacts" / "repo_summary.md"
        self.assertTrue(artifact_path.exists())
        artifact_text = artifact_path.read_text(encoding="utf-8")
        self.assertIn("# Repository Architecture Summary", artifact_text)
        self.assertIn("README: # Demo", artifact_text)
        self.assertEqual([event_type for event_type, _ in events[:2]], [
            "plan.updated",
            "subagent.started",
        ])
        self.assertIn("plan.updated", [event_type for event_type, _ in events[2:]])
        self.assertIn("tool.called", [event_type for event_type, _ in events])
        self.assertIn("Generated the requested architecture summary.", result.summary)


class FakeCompiledAgent:
    def __init__(self, kwargs: dict[str, Any], captures: dict[str, Any]) -> None:
        self._tools = kwargs["tools"]
        captures["agent_kwargs"] = kwargs

    def invoke(self, input: dict[str, Any]) -> dict[str, Any]:
        self._invoke_tool("list_files", {"root": "workspace"})
        readme = self._invoke_tool("read_file", {"path": "workspace/README.md"})
        pyproject = self._invoke_tool("read_file", {"path": "workspace/pyproject.toml"})
        self._invoke_tool(
            "write_file",
            {
                "path": "workspace/artifacts/repo_summary.md",
                "content": "\n".join(
                    [
                        "# Repository Architecture Summary",
                        "",
                        f"README: {readme.splitlines()[0]}",
                        f"Pyproject: {pyproject.splitlines()[1]}",
                    ]
                )
                + "\n",
            },
        )
        return {"messages": [{"role": "assistant", "content": "Generated the requested architecture summary."}]}

    def _invoke_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        for candidate in self._tools:
            if candidate.name == name:
                return candidate.invoke(arguments)
        raise AssertionError(f"missing tool: {name}")


if __name__ == "__main__":
    unittest.main()
