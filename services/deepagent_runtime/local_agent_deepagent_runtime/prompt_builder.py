from __future__ import annotations


class PromptBuilder:
    def build_system_prompt(
        self,
        *,
        identity_bundle_text: str,
        workspace_roots: list[str],
        objective: str,
        constraints: list[str] | None = None,
        success_criteria: list[str] | None = None,
        artifact_path: str = "artifacts/repo_summary.md",
    ) -> str:
        constraint_lines = _format_list(constraints or ["Honor sandbox and policy constraints."])
        success_lines = _format_list(
            success_criteria
            or [
                f"Create {artifact_path}.",
                "Summarize the repository structure, runtime, services, and protocol boundaries.",
            ]
        )
        workspace_lines = _format_list(workspace_roots)
        return "\n".join(
            [
                "You are the project-owned primary agent for Milestone 1.",
                "",
                "Identity Doctrine:",
                identity_bundle_text.strip(),
                "",
                "Objective:",
                objective.strip(),
                "",
                "Governed Workspace Roots:",
                workspace_lines,
                "",
                "Constraints:",
                constraint_lines,
                "",
                "Success Criteria:",
                success_lines,
                "",
                "Artifact Requirement:",
                f"- Write a Markdown architecture summary to {artifact_path}.",
                "- Keep runtime orchestration, sandbox mediation, and adapter isolation explicit.",
            ]
        ).strip()


def _format_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item.strip())
