from __future__ import annotations

from apps.runtime.local_agent_runtime.subagents import ResolvedSubagentConfiguration

MEMORY_PROMPT = "\n".join(
    [
        "Memory Behavior: ",
        "You wake up fresh each session. These files are your continuity:",
        "- **Daily notes:** `.memory/YYYY-MM-DD.md` — raw logs of what happened",
        "- **Long-term:** `MEMORY.md` — your curated memories, like a human's long-term memory",
        "Capture what matters. Decisions, context, things to remember. Skip the secrets unless asked to keep them.",
        "",
        "MEMORY.md - Your Long-Term Memory:",
        "- You can **read, edit, and update** MEMORY.md freely",
        "- Write significant events, thoughts, decisions, opinions, lessons learned",
        "- This is your curated memory — the distilled essence, not raw logs",
        "- Over time, review your daily files and update MEMORY.md with what's worth keeping",
        "",
        "Write It Down - No \"Mental Notes\"!",
        "- **Memory is limited** — if you want to remember something, WRITE IT TO A FILE",
        "- \"Mental notes\" don't survive session restarts. Files do.",
        "- When someone says \"remember this\" → update `.memory/YYYY-MM-DD.md` or relevant file",
        "- When you learn a lesson → update AGENTS.md, TOOLS.md, or the relevant skill",
        "- When you make a mistake → document it so future-you doesn't repeat it",
        "- **Text > Brain**",
        "",
    ]
)

class PromptBuilder:
    def build_primary_prompt(
        self,
        *,
        identity_bundle_text: str,
        workspace_roots: list[str],
        objective: str,
        constraints: list[str] | None = None,
        success_criteria: list[str] | None = None,
        available_roles: list[str] | None = None,
    ) -> str:
        constraint_lines = _format_list(constraints or ["Honor sandbox and policy constraints."])
        success_lines = _format_list(success_criteria or ["Satisfy the user objective."])
        role_lines = _format_list(
            available_roles or ["No project-owned subagents are configured for this run."]
        )
        _ = workspace_roots
        return "\n".join(
            [
                "You are the project-owned primary runtime agent.",
                "Use only governed tools and delegate specialized work through Deep Agent native subagents when they are available.",
                "The sandbox exposes a virtual filesystem with the governed workspace mounted at /workspace, /tmp for scratch space, and /.memory for runtime memory state.",
                "Do not use host filesystem paths such as /Users/...; treat /workspace as the primary accessible project root.",
                "",
                "Identity Doctrine:",
                identity_bundle_text.strip(),
                "",
                "Objective:",
                objective.strip(),
                "",
                "Accessible Workspace:",
                "- The governed workspace is mounted at /workspace.",
                "- Inspect files with virtual paths such as /workspace/people.csv.",
                "- Do not reference host paths from the runtime configuration or task metadata.",
                "",
                MEMORY_PROMPT,
                "Constraints:",
                constraint_lines,
                "",
                "Success Criteria:",
                success_lines,
                "",
                "Available Subagent Roles:",
                role_lines,
            ]
        ).strip()

    def build_subagent_prompt(
        self,
        *,
        resolved: ResolvedSubagentConfiguration,
        identity_bundle_text: str,
    ) -> str:
        definition = resolved.asset_bundle.definition
        return "\n".join(
            [
                "Runtime Governance:",
                "Operate inside the project-owned runtime boundary. Use only your scoped tools, respect policy and sandbox controls, and do not claim capabilities you do not have.",
                "The virtual filesystem exposes /workspace for project files, /tmp for scratch space, and /.memory for runtime memory state.",
                "",
                MEMORY_PROMPT,
                "Primary Identity Doctrine:",
                identity_bundle_text.strip(),
                "",
                "Role Identity:",
                (
                    resolved.asset_bundle.identity_text or "No additional role identity provided."
                ).strip(),
                "",
                "Role Overlay:",
                (
                    resolved.asset_bundle.system_prompt_text
                    or "No additional role system overlay provided."
                ).strip(),
                "",
                "Scope Summary:",
                _format_list(
                    [
                        f"role_id: {definition.role_id}",
                        f"role_name: {definition.name}",
                        f"description: {definition.description}",
                        f"resolved_model: {resolved.model_route.provider}/{resolved.model_route.model}",
                        f"model_source: {resolved.model_route.source}",
                        f"tool_scope: {', '.join(binding.tool_id for binding in resolved.tool_bindings) or 'none'}",
                        f"memory_scope: {', '.join(definition.memory_scope) or 'none'}",
                        f"filesystem_scope: {', '.join(definition.filesystem_scope) or 'none'}",
                        f"skills: {', '.join(skill.skill_id for skill in resolved.skills) or 'none'}",
                    ]
                ),
            ]
        ).strip()


def _format_list(items: list[str]) -> str:
    filtered = [item.strip() for item in items if item and item.strip()]
    return "\n".join(f"- {item}" for item in filtered)
