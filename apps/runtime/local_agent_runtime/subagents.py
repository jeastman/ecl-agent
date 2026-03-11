from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


ALLOWED_SUBAGENT_TOOL_IDS = frozenset(
    {
        "artifact_inspect",
        "execute_commands",
        "memory_lookup",
        "plan_update",
        "read_files",
        "write_files",
    }
)
ALLOWED_MEMORY_SCOPES = frozenset({"project", "run"})
ALLOWED_FILESYSTEM_SCOPES = frozenset({"memory", "workspace"})


@dataclass(frozen=True, slots=True)
class SubagentDefinition:
    role_id: str
    name: str
    description: str
    model_profile: str | None
    tool_scope: tuple[str, ...]
    memory_scope: tuple[str, ...]
    filesystem_scope: tuple[str, ...]
    identity_path: Path | None
    system_prompt_path: Path | None
    skills_path: Path | None


@dataclass(frozen=True, slots=True)
class SubagentAssetBundle:
    definition: SubagentDefinition
    identity_text: str | None
    system_prompt_text: str | None


class SubagentRegistry(Protocol):
    def list_roles(self) -> list[str]: ...

    def get_definition(self, role_id: str) -> SubagentDefinition: ...

    def get_asset_bundle(self, role_id: str) -> SubagentAssetBundle: ...

    def list_asset_bundles(self) -> list[SubagentAssetBundle]: ...
