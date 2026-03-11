from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from apps.runtime.local_agent_runtime.subagents import (
    ALLOWED_FILESYSTEM_SCOPES,
    ALLOWED_MEMORY_SCOPES,
    ALLOWED_SUBAGENT_TOOL_IDS,
    SubagentAssetBundle,
    SubagentDefinition,
)


class SubagentRegistryError(ValueError):
    pass


class FileSystemSubagentRegistry:
    def __init__(self, root_path: str | Path) -> None:
        self._root_path = Path(root_path).resolve()
        self._definitions: dict[str, SubagentDefinition] = {}
        self._asset_bundles: dict[str, SubagentAssetBundle] = {}
        self._load()

    def list_roles(self) -> list[str]:
        return list(self._definitions)

    def get_definition(self, role_id: str) -> SubagentDefinition:
        try:
            return self._definitions[role_id]
        except KeyError as exc:
            raise SubagentRegistryError(f"Unknown subagent role: {role_id}") from exc

    def get_asset_bundle(self, role_id: str) -> SubagentAssetBundle:
        try:
            return self._asset_bundles[role_id]
        except KeyError as exc:
            raise SubagentRegistryError(f"Unknown subagent role: {role_id}") from exc

    def list_asset_bundles(self) -> list[SubagentAssetBundle]:
        return [self._asset_bundles[role_id] for role_id in self.list_roles()]

    def _load(self) -> None:
        if not self._root_path.exists():
            raise SubagentRegistryError(f"Subagent root does not exist: {self._root_path}")
        if not self._root_path.is_dir():
            raise SubagentRegistryError(f"Subagent root is not a directory: {self._root_path}")

        seen_role_ids: set[str] = set()
        mismatched_roles: list[tuple[str, str]] = []
        for role_dir in sorted(self._root_path.iterdir(), key=lambda path: path.name):
            if not role_dir.is_dir():
                raise SubagentRegistryError(
                    f"Subagent registry entry must be a directory: {role_dir.name}"
                )
            definition, asset_bundle, directory_name = self._load_role(role_dir, seen_role_ids)
            seen_role_ids.add(definition.role_id)
            self._definitions[definition.role_id] = definition
            self._asset_bundles[definition.role_id] = asset_bundle
            if definition.role_id != directory_name:
                mismatched_roles.append((definition.role_id, directory_name))
        if mismatched_roles:
            role_id, directory_name = mismatched_roles[0]
            raise SubagentRegistryError(
                f"Subagent role_id '{role_id}' does not match directory '{directory_name}'"
            )

    def _load_role(
        self, role_dir: Path, seen_role_ids: set[str]
    ) -> tuple[SubagentDefinition, SubagentAssetBundle, str]:
        manifest_path = role_dir / "manifest.yaml"
        if not manifest_path.is_file():
            raise SubagentRegistryError(f"Subagent role '{role_dir.name}' is missing manifest.yaml")

        manifest = self._load_manifest(manifest_path)
        role_id = self._read_required_string(manifest, "role_id", manifest_path)
        if role_id in seen_role_ids:
            raise SubagentRegistryError(f"Duplicate subagent role_id: {role_id}")

        definition = SubagentDefinition(
            role_id=role_id,
            name=self._read_required_string(manifest, "name", manifest_path),
            description=self._read_required_string(manifest, "description", manifest_path),
            model_profile=self._read_optional_string(manifest, "model_profile", manifest_path),
            tool_scope=self._read_string_sequence(
                manifest,
                key="tool_scope",
                manifest_path=manifest_path,
                allowed_values=ALLOWED_SUBAGENT_TOOL_IDS,
            ),
            memory_scope=self._read_string_sequence(
                manifest,
                key="memory_scope",
                manifest_path=manifest_path,
                allowed_values=ALLOWED_MEMORY_SCOPES,
            ),
            filesystem_scope=self._read_string_sequence(
                manifest,
                key="filesystem_scope",
                manifest_path=manifest_path,
                allowed_values=ALLOWED_FILESYSTEM_SCOPES,
            ),
            identity_path=self._optional_file_path(role_dir / "IDENTITY.md"),
            system_prompt_path=self._optional_file_path(role_dir / "SYSTEM_PROMPT.md"),
            skills_path=self._optional_directory_path(role_dir / "skills"),
            role_root_path=role_dir,
        )
        asset_bundle = SubagentAssetBundle(
            definition=definition,
            identity_text=self._read_optional_text(role_dir / "IDENTITY.md"),
            system_prompt_text=self._read_optional_text(role_dir / "SYSTEM_PROMPT.md"),
        )
        return definition, asset_bundle, role_dir.name

    def _load_manifest(self, manifest_path: Path) -> dict[str, object]:
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise SubagentRegistryError(
                f"Unable to read subagent manifest: {manifest_path}"
            ) from exc
        except yaml.YAMLError as exc:
            raise SubagentRegistryError(
                f"Invalid YAML in subagent manifest: {manifest_path}"
            ) from exc

        if not isinstance(manifest, dict):
            raise SubagentRegistryError(f"Subagent manifest must be a mapping: {manifest_path}")
        return manifest

    def _read_required_string(
        self, manifest: dict[str, object], key: str, manifest_path: Path
    ) -> str:
        value = manifest.get(key)
        if not isinstance(value, str) or not value.strip():
            raise SubagentRegistryError(
                f"Subagent manifest field '{key}' must be a non-empty string: {manifest_path}"
            )
        return value

    def _read_optional_string(
        self, manifest: dict[str, object], key: str, manifest_path: Path
    ) -> str | None:
        if key not in manifest or manifest[key] is None:
            return None
        value = manifest[key]
        if not isinstance(value, str) or not value.strip():
            raise SubagentRegistryError(
                f"Subagent manifest field '{key}' must be a string when present: {manifest_path}"
            )
        return value

    def _read_string_sequence(
        self,
        manifest: dict[str, object],
        *,
        key: str,
        manifest_path: Path,
        allowed_values: frozenset[str],
    ) -> tuple[str, ...]:
        value = manifest.get(key)
        if not isinstance(value, list):
            raise SubagentRegistryError(
                f"Subagent manifest field '{key}' must be a list: {manifest_path}"
            )

        items: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise SubagentRegistryError(
                    f"Subagent manifest field '{key}' must contain non-empty strings: {manifest_path}"
                )
            if item not in allowed_values:
                raise SubagentRegistryError(f"Unknown {key} value '{item}' in {manifest_path}")
            items.append(item)
        return tuple(items)

    def _optional_file_path(self, path: Path) -> Path | None:
        if not path.exists():
            return None
        if not path.is_file():
            raise SubagentRegistryError(f"Subagent asset is not a readable file: {path}")
        return path

    def _optional_directory_path(self, path: Path) -> Path | None:
        if not path.exists():
            return None
        if not path.is_dir():
            raise SubagentRegistryError(f"Subagent skills path is not a directory: {path}")
        return path

    def _read_optional_text(self, path: Path) -> str | None:
        file_path = self._optional_file_path(path)
        if file_path is None:
            return None
        try:
            return file_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SubagentRegistryError(f"Unable to read subagent asset: {path}") from exc
