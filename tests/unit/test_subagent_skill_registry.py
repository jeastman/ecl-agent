from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.runtime.local_agent_runtime.subagents import SubagentDefinition
from services.subagent_runtime.local_agent_subagent_runtime.skill_registry import (
    FileSystemSkillRegistry,
    SkillRegistryError,
)


class FileSystemSkillRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = FileSystemSkillRegistry()

    def test_missing_skills_directory_returns_empty_descriptors(self) -> None:
        definition = _definition(None)

        descriptors = self.registry.list_skill_descriptors(definition)

        self.assertEqual(descriptors, ())

    def test_discovers_directory_and_file_skills(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            skills_path = Path(temp_dir) / "skills"
            skills_path.mkdir()
            skill_dir = skills_path / "repo-map"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Repo Map\n", encoding="utf-8")
            (skills_path / "quick-check.md").write_text("# Quick Check\n", encoding="utf-8")
            (skills_path / ".gitkeep").write_text("", encoding="utf-8")

            descriptors = self.registry.list_skill_descriptors(_definition(skills_path))

            self.assertEqual(
                [descriptor.skill_id for descriptor in descriptors], ["quick-check", "repo-map"]
            )
            self.assertEqual(descriptors[0].source, "file")
            self.assertEqual(descriptors[0].prompt_text, "# Quick Check")
            self.assertEqual(descriptors[1].source, "directory")
            self.assertEqual(descriptors[1].prompt_text, "# Repo Map")

    def test_invalid_skill_directory_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            skills_path = Path(temp_dir) / "skills"
            skills_path.mkdir()
            (skills_path / "broken-skill").mkdir()

            with self.assertRaisesRegex(SkillRegistryError, "missing SKILL.md"):
                self.registry.list_skill_descriptors(_definition(skills_path))

    def test_discovery_is_isolated_per_role(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            planner_skills = root / "planner-skills"
            planner_skills.mkdir()
            (planner_skills / "planner.md").write_text("# Planner\n", encoding="utf-8")
            coder_skills = root / "coder-skills"
            coder_skills.mkdir()
            (coder_skills / "coder.md").write_text("# Coder\n", encoding="utf-8")

            planner_descriptors = self.registry.list_skill_descriptors(_definition(planner_skills))
            coder_descriptors = self.registry.list_skill_descriptors(_definition(coder_skills))

            self.assertEqual(
                [descriptor.skill_id for descriptor in planner_descriptors], ["planner"]
            )
            self.assertEqual([descriptor.skill_id for descriptor in coder_descriptors], ["coder"])

    def test_primary_agent_skill_directory_uses_shared_loader(self) -> None:
        descriptors = self.registry.list_skill_descriptors_for_path(
            Path("agents/primary-agent/skills")
        )

        self.assertEqual(
            [descriptor.skill_id for descriptor in descriptors], ["runtime-governance"]
        )


def _definition(skills_path: Path | None) -> SubagentDefinition:
    return SubagentDefinition(
        role_id="planner",
        name="Planner",
        description="Plan work.",
        model_profile="planner",
        tool_scope=("read_files",),
        memory_scope=("run",),
        filesystem_scope=("workspace",),
        identity_path=None,
        system_prompt_path=None,
        skills_path=skills_path,
    )


if __name__ == "__main__":
    unittest.main()
