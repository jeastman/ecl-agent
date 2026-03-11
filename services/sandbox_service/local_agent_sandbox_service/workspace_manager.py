from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.sandbox_service.local_agent_sandbox_service.path_policy import ensure_within_root


@dataclass(frozen=True, slots=True)
class SandboxRoots:
    workspace_root: Path
    scratch_root: Path
    memory_root: Path
    allowed_workspace_roots: tuple[Path, ...]


class WorkspaceManager:
    def __init__(self, runtime_root: Path) -> None:
        self._runtime_root = runtime_root.resolve()

    def create_roots(
        self, *, task_id: str, run_id: str, workspace_roots: list[str]
    ) -> SandboxRoots:
        if not workspace_roots:
            raise ValueError("task requires at least one workspace root")
        resolved_workspace_roots = tuple(
            ensure_within_root(Path.cwd(), Path(candidate).resolve())
            for candidate in workspace_roots
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
        )
