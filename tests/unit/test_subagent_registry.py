from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from apps.runtime.local_agent_runtime.subagents import (
    ALLOWED_SUBAGENT_TOOL_IDS,
    SubagentAssetBundle,
    SubagentDefinition,
)
from services.subagent_registry.local_agent_subagent_registry.filesystem_subagent_registry import (
    FileSystemSubagentRegistry,
    SubagentRegistryError,
)


class FileSystemSubagentRegistryTests(unittest.TestCase):
    def test_loads_repository_baseline_roles(self) -> None:
        registry = FileSystemSubagentRegistry(Path("agents/subagents"))

        self.assertEqual(
            registry.list_roles(),
            ["coder", "librarian", "planner", "researcher", "verifier"],
        )
        planner = registry.get_definition("planner")
        self.assertIsInstance(planner, SubagentDefinition)
        self.assertEqual(planner.tool_scope, ("read_files", "memory_lookup", "plan_update"))
        self.assertEqual(planner.memory_scope, ("run", "project"))
        self.assertIsNotNone(planner.skills_path)
        planner_bundle = registry.get_asset_bundle("planner")
        self.assertIsInstance(planner_bundle, SubagentAssetBundle)
        self.assertIn("Planner", planner_bundle.identity_text or "")
        self.assertIn("execution plan", planner_bundle.system_prompt_text or "")

    def test_optional_assets_can_be_absent(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            self._write_role(
                root / "planner",
                """
                role_id: planner
                name: Planner
                description: Plan work.
                tool_scope:
                  - read_files
                memory_scope:
                  - run
                filesystem_scope:
                  - workspace
                """,
            )

            registry = FileSystemSubagentRegistry(root)
            definition = registry.get_definition("planner")
            bundle = registry.get_asset_bundle("planner")

            self.assertIsNone(definition.identity_path)
            self.assertIsNone(definition.system_prompt_path)
            self.assertIsNone(definition.skills_path)
            self.assertIsNone(bundle.identity_text)
            self.assertIsNone(bundle.system_prompt_text)

    def test_rejects_missing_manifest(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            role_dir = Path(temp_dir) / "planner"
            role_dir.mkdir()

            with self.assertRaisesRegex(SubagentRegistryError, "missing manifest.yaml"):
                FileSystemSubagentRegistry(Path(temp_dir))

    def test_rejects_missing_role_id(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            self._write_role(
                Path(temp_dir) / "planner",
                """
                name: Planner
                description: Plan work.
                tool_scope:
                  - read_files
                memory_scope:
                  - run
                filesystem_scope:
                  - workspace
                """,
            )

            with self.assertRaisesRegex(SubagentRegistryError, "field 'role_id'"):
                FileSystemSubagentRegistry(Path(temp_dir))

    def test_rejects_directory_name_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            self._write_role(
                Path(temp_dir) / "planner-copy",
                """
                role_id: planner
                name: Planner
                description: Plan work.
                tool_scope:
                  - read_files
                memory_scope:
                  - run
                filesystem_scope:
                  - workspace
                """,
            )

            with self.assertRaisesRegex(SubagentRegistryError, "does not match directory"):
                FileSystemSubagentRegistry(Path(temp_dir))

    def test_rejects_duplicate_role_ids_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            self._write_role(
                root / "a-planner",
                """
                role_id: planner
                name: Planner A
                description: Plan work.
                tool_scope:
                  - read_files
                memory_scope:
                  - run
                filesystem_scope:
                  - workspace
                """,
            )
            self._write_role(
                root / "b-planner",
                """
                role_id: planner
                name: Planner B
                description: Plan work too.
                tool_scope:
                  - read_files
                memory_scope:
                  - run
                filesystem_scope:
                  - workspace
                """,
            )

            with self.assertRaisesRegex(SubagentRegistryError, "Duplicate subagent role_id: planner"):
                FileSystemSubagentRegistry(root)

    def test_rejects_unknown_tool_identifier(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            self._write_role(
                Path(temp_dir) / "planner",
                """
                role_id: planner
                name: Planner
                description: Plan work.
                tool_scope:
                  - invent_tools
                memory_scope:
                  - run
                filesystem_scope:
                  - workspace
                """,
            )

            with self.assertRaisesRegex(SubagentRegistryError, "Unknown tool_scope value 'invent_tools'"):
                FileSystemSubagentRegistry(Path(temp_dir))

    def test_rejects_invalid_memory_scope(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            self._write_role(
                Path(temp_dir) / "planner",
                """
                role_id: planner
                name: Planner
                description: Plan work.
                tool_scope:
                  - read_files
                memory_scope:
                  - identity
                filesystem_scope:
                  - workspace
                """,
            )

            with self.assertRaisesRegex(SubagentRegistryError, "Unknown memory_scope value 'identity'"):
                FileSystemSubagentRegistry(Path(temp_dir))

    def test_rejects_invalid_filesystem_scope(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            self._write_role(
                Path(temp_dir) / "planner",
                """
                role_id: planner
                name: Planner
                description: Plan work.
                tool_scope:
                  - read_files
                memory_scope:
                  - run
                filesystem_scope:
                  - repo
                """,
            )

            with self.assertRaisesRegex(SubagentRegistryError, "Unknown filesystem_scope value 'repo'"):
                FileSystemSubagentRegistry(Path(temp_dir))

    def test_rejects_unreadable_optional_asset(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            role_dir = Path(temp_dir) / "planner"
            self._write_role(
                role_dir,
                """
                role_id: planner
                name: Planner
                description: Plan work.
                tool_scope:
                  - read_files
                memory_scope:
                  - run
                filesystem_scope:
                  - workspace
                """,
            )
            (role_dir / "IDENTITY.md").mkdir()

            with self.assertRaisesRegex(SubagentRegistryError, "readable file"):
                FileSystemSubagentRegistry(Path(temp_dir))

    def test_rejects_non_directory_entries(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "README.txt").write_text("not a role", encoding="utf-8")

            with self.assertRaisesRegex(SubagentRegistryError, "must be a directory"):
                FileSystemSubagentRegistry(root)

    def test_runtime_contracts_do_not_reference_framework_types(self) -> None:
        subagent_source = Path("apps/runtime/local_agent_runtime/subagents.py").read_text(
            encoding="utf-8"
        )
        registry_source = Path(
            "services/subagent_registry/local_agent_subagent_registry/filesystem_subagent_registry.py"
        ).read_text(encoding="utf-8")

        self.assertTrue({"read_files", "write_files"}.issubset(ALLOWED_SUBAGENT_TOOL_IDS))
        self.assertNotIn("langchain", subagent_source.lower())
        self.assertNotIn("deepagent", subagent_source.lower())
        self.assertNotIn("langchain", registry_source.lower())
        self.assertNotIn("deepagent", registry_source.lower())

    def _write_role(self, role_dir: Path, manifest_text: str) -> None:
        role_dir.mkdir(parents=True)
        (role_dir / "manifest.yaml").write_text(
            textwrap.dedent(manifest_text).strip() + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
