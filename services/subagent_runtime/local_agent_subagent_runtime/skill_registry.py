from __future__ import annotations

from pathlib import Path

from apps.runtime.local_agent_runtime.subagents import SkillDescriptor, SubagentDefinition


class SkillRegistryError(ValueError):
    pass


class FileSystemSkillRegistry:
    def list_skill_descriptors(self, definition: SubagentDefinition) -> tuple[SkillDescriptor, ...]:
        return self.list_skill_descriptors_for_path(definition.skills_path)

    def list_skill_descriptors_for_path(
        self, skills_path: Path | None
    ) -> tuple[SkillDescriptor, ...]:
        if skills_path is None:
            return ()
        if not skills_path.exists() or not skills_path.is_dir():
            raise SkillRegistryError(f"Skill path is not a directory: {skills_path}")

        descriptors: list[SkillDescriptor] = []
        for entry in sorted(skills_path.iterdir(), key=lambda path: path.name):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                prompt_path = entry / "SKILL.md"
                if not prompt_path.is_file():
                    raise SkillRegistryError(f"Skill directory is missing SKILL.md: {entry}")
                descriptors.append(
                    SkillDescriptor(
                        skill_id=entry.name,
                        name=_display_name(entry.stem),
                        prompt_path=prompt_path,
                        source="directory",
                        prompt_text=_read_prompt_text(prompt_path),
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
                        prompt_text=_read_prompt_text(entry),
                    )
                )
                continue
            raise SkillRegistryError(f"Unsupported skill asset: {entry}")
        return tuple(descriptors)


def _display_name(value: str) -> str:
    return value.replace("-", " ").replace("_", " ").strip() or value


def _read_prompt_text(path: Path) -> str:
    try:
        prompt_text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SkillRegistryError(f"Unable to read skill prompt: {path}") from exc
    if not prompt_text:
        raise SkillRegistryError(f"Skill prompt is empty: {path}")
    return prompt_text
