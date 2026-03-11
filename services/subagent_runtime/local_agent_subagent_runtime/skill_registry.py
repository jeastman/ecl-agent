from __future__ import annotations

from apps.runtime.local_agent_runtime.subagents import SkillDescriptor, SubagentDefinition


class SkillRegistryError(ValueError):
    pass


class FileSystemSkillRegistry:
    def list_skill_descriptors(self, definition: SubagentDefinition) -> tuple[SkillDescriptor, ...]:
        skills_path = definition.skills_path
        if skills_path is None:
            return ()
        if not skills_path.exists() or not skills_path.is_dir():
            raise SkillRegistryError(f"Subagent skills path is not a directory: {skills_path}")

        descriptors: list[SkillDescriptor] = []
        for entry in sorted(skills_path.iterdir(), key=lambda path: path.name):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                prompt_path = entry / "SKILL.md"
                if not prompt_path.is_file():
                    raise SkillRegistryError(
                        f"Subagent skill directory is missing SKILL.md: {entry}"
                    )
                descriptors.append(
                    SkillDescriptor(
                        skill_id=entry.name,
                        name=_display_name(entry.stem),
                        prompt_path=prompt_path,
                        source="directory",
                    )
                )
                continue
            if entry.is_file() and entry.suffix.lower() == ".md":
                descriptors.append(
                    SkillDescriptor(
                        skill_id=entry.stem,
                        name=_display_name(entry.stem),
                        prompt_path=entry,
                        source="file",
                    )
                )
                continue
            raise SkillRegistryError(f"Unsupported subagent skill asset: {entry}")
        return tuple(descriptors)


def _display_name(value: str) -> str:
    return value.replace("-", " ").replace("_", " ").strip() or value
