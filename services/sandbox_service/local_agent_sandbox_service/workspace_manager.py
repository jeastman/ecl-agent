from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from services.sandbox_service.local_agent_sandbox_service.path_policy import (
    WORKSPACE_MOUNT,
    ensure_within_root,
    normalize_workspace_virtual_root,
)


@dataclass(frozen=True, slots=True)
class SandboxRoots:
    workspace_root: Path
    scratch_root: Path
    memory_root: Path
    allowed_workspace_roots: tuple[Path, ...]
    virtual_workspace_root: PurePosixPath
    allowed_virtual_workspace_roots: tuple[PurePosixPath, ...]


class WorkspaceManager:
    def __init__(
        self,
        runtime_root: Path,
        governed_workspace_root: Path,
        virtual_workspace_root: str = WORKSPACE_MOUNT.as_posix(),
    ) -> None:
        self._runtime_root = runtime_root.resolve()
        self._governed_workspace_root = governed_workspace_root.resolve()
        self._virtual_workspace_root = PurePosixPath(
            normalize_workspace_virtual_root(virtual_workspace_root)
        )

    def create_roots(
        self, *, task_id: str, run_id: str, workspace_roots: list[str]
    ) -> SandboxRoots:
        resolved_virtual_roots = self.normalize_workspace_roots(workspace_roots)
        resolved_workspace_roots = tuple(
            ensure_within_root(
                self._governed_workspace_root,
                self._governed_workspace_root
                / virtual_root.relative_to(self._virtual_workspace_root),
            )
            for virtual_root in resolved_virtual_roots
        )
        scratch_root = self._runtime_root / "scratch" / task_id / run_id
        memory_root = self._runtime_root / "memory" / task_id
        scratch_root.mkdir(parents=True, exist_ok=True)
        memory_root.mkdir(parents=True, exist_ok=True)
        return SandboxRoots(
            workspace_root=resolved_workspace_roots[0],
            scratch_root=scratch_root.resolve(),
            memory_root=memory_root.resolve(),
            allowed_workspace_roots=resolved_workspace_roots,
            virtual_workspace_root=self._virtual_workspace_root,
            allowed_virtual_workspace_roots=resolved_virtual_roots,
        )

    def normalize_workspace_roots(self, workspace_roots: list[str]) -> tuple[PurePosixPath, ...]:
        if not workspace_roots:
            raise ValueError("task requires at least one workspace root")
        resolved_virtual_roots = tuple(
            PurePosixPath(normalize_workspace_virtual_root(candidate))
            for candidate in workspace_roots
        )
        normalized: list[PurePosixPath] = []
        for candidate in resolved_virtual_roots:
            if any(
                candidate == existing
                or candidate.is_relative_to(existing)
                or existing.is_relative_to(candidate)
                for existing in normalized
            ):
                raise ValueError("workspace roots must be distinct non-overlapping virtual paths")
            normalized.append(candidate)
        return tuple(normalized)
