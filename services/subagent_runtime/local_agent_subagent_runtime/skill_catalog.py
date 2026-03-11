from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apps.runtime.local_agent_runtime.subagents import (
    ResolvedSubagentConfiguration,
    SkillDescriptor,
    ToolResolutionContext,
)
from services.subagent_registry.local_agent_subagent_registry.filesystem_subagent_registry import (
    FileSystemSubagentRegistry,
)
from services.subagent_runtime.local_agent_subagent_runtime.model_routing import (
    RuntimeModelResolver,
)
from services.subagent_runtime.local_agent_subagent_runtime.skill_registry import (
    FileSystemSkillRegistry,
)
from services.subagent_runtime.local_agent_subagent_runtime.tool_scope import (
    RoleToolScopeResolver,
)


@dataclass(frozen=True, slots=True)
class SkillInstallTarget:
    target_scope: str
    managed_root: Path
    role_id: str | None = None


class RuntimeSkillCatalog:
    def __init__(
        self,
        *,
        identity_path: str | Path,
        subagent_registry: FileSystemSubagentRegistry,
        model_resolver: RuntimeModelResolver,
        tool_scope_resolver: RoleToolScopeResolver,
        skill_registry: FileSystemSkillRegistry,
    ) -> None:
        self._identity_path = Path(identity_path).resolve()
        self._subagent_registry = subagent_registry
        self._model_resolver = model_resolver
        self._tool_scope_resolver = tool_scope_resolver
        self._skill_registry = skill_registry

    def primary_skills_path(self) -> Path:
        return self._identity_path.parent / "skills"

    def load_primary_skills(self) -> tuple[SkillDescriptor, ...]:
        path = self.primary_skills_path()
        if not path.exists():
            return ()
        return self._skill_registry.list_skill_descriptors_for_path(path)

    def resolve_subagents(self) -> list[ResolvedSubagentConfiguration]:
        resolved: list[ResolvedSubagentConfiguration] = []
        for asset_bundle in self._subagent_registry.list_asset_bundles():
            definition = asset_bundle.definition
            resolved.append(
                ResolvedSubagentConfiguration(
                    asset_bundle=asset_bundle,
                    model_route=self._model_resolver.resolve_subagent(
                        definition.role_id,
                        definition.model_profile,
                    ),
                    tool_bindings=self._tool_scope_resolver.resolve_tools(
                        definition,
                        ToolResolutionContext(),
                    ),
                    skills=self._skill_registry.list_skill_descriptors_for_path(
                        self.skills_path_for_role(definition.role_id)
                    ),
                )
            )
        return resolved

    def resolve_install_target(
        self, target_scope: str, target_role: str | None
    ) -> SkillInstallTarget:
        if target_scope == "primary_agent":
            return SkillInstallTarget(
                target_scope=target_scope,
                managed_root=self.primary_skills_path(),
                role_id=None,
            )
        if target_scope != "subagent":
            raise ValueError("skill.install target_scope must be primary_agent or subagent")
        if target_role is None or not target_role.strip():
            raise ValueError("skill.install target_role is required for subagent installs")
        role_id = target_role.strip()
        definition = self._subagent_registry.get_definition(role_id)
        return SkillInstallTarget(
            target_scope=target_scope,
            managed_root=self.skills_path_for_role(definition.role_id),
            role_id=definition.role_id,
        )

    def skills_path_for_role(self, role_id: str) -> Path:
        definition = self._subagent_registry.get_definition(role_id)
        if definition.skills_path is not None:
            return definition.skills_path
        if definition.role_root_path is None:
            raise ValueError(f"Subagent role has no managed root path: {role_id}")
        return definition.role_root_path / "skills"
