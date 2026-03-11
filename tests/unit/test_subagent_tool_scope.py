from __future__ import annotations

import unittest

from apps.runtime.local_agent_runtime.subagents import SubagentDefinition, ToolResolutionContext
from services.subagent_runtime.local_agent_subagent_runtime.tool_scope import (
    RoleToolScopeResolver,
)


class RoleToolScopeResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = RoleToolScopeResolver()

    def test_planner_resolves_expected_tools(self) -> None:
        tools = self.resolver.resolve_tools(_role("planner", ("read_files", "memory_lookup", "plan_update")))

        self.assertEqual([tool.tool_id for tool in tools], ["read_files", "memory_lookup", "plan_update"])

    def test_coder_resolves_expected_tools(self) -> None:
        tools = self.resolver.resolve_tools(
            _role("coder", ("read_files", "write_files", "execute_commands"))
        )

        self.assertEqual([tool.tool_id for tool in tools], ["read_files", "write_files", "execute_commands"])
        self.assertTrue(all(tool.requires_policy for tool in tools))

    def test_verifier_resolves_expected_tools(self) -> None:
        tools = self.resolver.resolve_tools(
            _role("verifier", ("read_files", "execute_commands", "artifact_inspect"))
        )

        self.assertEqual([tool.tool_id for tool in tools], ["read_files", "execute_commands", "artifact_inspect"])
        self.assertEqual(tools[-1].capability_aliases, ("artifact_inspect", "artifacts", "artifacts.read"))

    def test_researcher_resolves_expected_tools(self) -> None:
        tools = self.resolver.resolve_tools(
            _role("researcher", ("read_files", "memory_lookup"))
        )

        self.assertEqual([tool.tool_id for tool in tools], ["read_files", "memory_lookup"])

    def test_librarian_resolves_expected_tools(self) -> None:
        tools = self.resolver.resolve_tools(
            _role("librarian", ("read_files", "memory_lookup"))
        )

        self.assertEqual([tool.tool_id for tool in tools], ["read_files", "memory_lookup"])

    def test_task_capabilities_can_only_reduce_declared_scope(self) -> None:
        tools = self.resolver.resolve_tools(
            _role("planner", ("read_files", "memory_lookup", "plan_update")),
            ToolResolutionContext(allowed_capabilities=("memory_lookup",)),
        )

        self.assertEqual([tool.tool_id for tool in tools], ["memory_lookup"])

    def test_resolved_bindings_preserve_policy_markers(self) -> None:
        tools = self.resolver.resolve_tools(
            _role("mixed", ("read_files", "memory_lookup", "execute_commands"))
        )

        requires_policy = {tool.tool_id: tool.requires_policy for tool in tools}
        self.assertEqual(
            requires_policy,
            {
                "read_files": True,
                "memory_lookup": False,
                "execute_commands": True,
            },
        )


def _role(role_id: str, tool_scope: tuple[str, ...]) -> SubagentDefinition:
    return SubagentDefinition(
        role_id=role_id,
        name=role_id.title(),
        description=f"{role_id} description",
        model_profile=role_id,
        tool_scope=tool_scope,
        memory_scope=("run",),
        filesystem_scope=("workspace",),
        identity_path=None,
        system_prompt_path=None,
        skills_path=None,
    )


if __name__ == "__main__":
    unittest.main()
