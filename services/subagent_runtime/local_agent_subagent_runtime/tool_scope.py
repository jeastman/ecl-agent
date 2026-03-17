from __future__ import annotations

from apps.runtime.local_agent_runtime.subagents import (
    ResolvedToolBinding,
    SubagentDefinition,
    ToolResolutionContext,
)

_TOOL_CAPABILITY_ALIASES: dict[str, tuple[str, ...]] = {
    "read_files": ("read_file", "list_files", "filesystem", "files.read", "files.list"),
    "write_files": ("write_file", "filesystem", "files.write"),
    "execute_commands": ("execute_command", "commands", "sandbox.execute"),
    "memory_lookup": ("memory_lookup", "memory", "memory.read"),
    "plan_update": ("plan_update", "planning", "plan.write"),
    "artifact_inspect": ("artifact_inspect", "artifacts", "artifacts.read"),
    "web_fetch": ("web_fetch", "web.fetch", "web"),
    "web_search": ("web_search", "web.search", "web"),
}


class RoleToolScopeResolver:
    def resolve_tools(
        self,
        role: SubagentDefinition,
        task_context: ToolResolutionContext | None = None,
    ) -> tuple[ResolvedToolBinding, ...]:
        allowed_capabilities = {
            item.strip()
            for item in (task_context.allowed_capabilities if task_context is not None else ())
            if item and item.strip()
        }
        bindings: list[ResolvedToolBinding] = []
        for tool_id in role.tool_scope:
            aliases = _TOOL_CAPABILITY_ALIASES[tool_id]
            if allowed_capabilities and allowed_capabilities.isdisjoint(aliases):
                continue
            bindings.append(
                ResolvedToolBinding(
                    tool_id=tool_id,
                    capability_aliases=aliases,
                    requires_policy=tool_id
                    in {"read_files", "write_files", "execute_commands", "web_fetch", "web_search"},
                )
            )
        return tuple(bindings)
