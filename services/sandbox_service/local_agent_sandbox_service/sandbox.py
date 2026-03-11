from __future__ import annotations

from pathlib import Path
from typing import Protocol

from services.sandbox_service.local_agent_sandbox_service.command_executor import CommandExecutor
from services.sandbox_service.local_agent_sandbox_service.models import CommandResult
from services.sandbox_service.local_agent_sandbox_service.path_policy import (
    ZONE_MEMORY,
    ZONE_SCRATCH,
    ZONE_WORKSPACE,
    NormalizedSandboxPath,
    ensure_within_root,
    normalize_sandbox_path,
)
from services.sandbox_service.local_agent_sandbox_service.workspace_manager import (
    SandboxRoots,
    WorkspaceManager,
)


class ExecutionSandbox(Protocol):
    def get_workspace_root(self) -> str: ...

    def get_scratch_root(self) -> str: ...

    def get_memory_root(self) -> str: ...

    def normalize_path(self, path: str) -> str: ...

    def read_text(self, path: str) -> str: ...

    def write_text(self, path: str, content: str) -> None: ...

    def exists(self, path: str) -> bool: ...

    def list_files(self, root: str) -> list[str]: ...

    def execute_command(self, command: list[str], cwd: str | None = None) -> CommandResult: ...


class SandboxPathMapper(Protocol):
    def materialize_artifact_path(
        self,
        *,
        task_id: str,
        run_id: str,
        sandbox_path: str,
    ) -> tuple[str, Path, str]: ...


class LocalExecutionSandboxFactory(SandboxPathMapper):
    def __init__(self, runtime_root: str | Path) -> None:
        self._workspace_manager = WorkspaceManager(Path(runtime_root))
        self._roots_by_run: dict[tuple[str, str], SandboxRoots] = {}
        Path(runtime_root).mkdir(parents=True, exist_ok=True)

    def for_run(
        self, *, task_id: str, run_id: str, workspace_roots: list[str]
    ) -> "LocalExecutionSandbox":
        roots = self._workspace_manager.create_roots(
            task_id=task_id,
            run_id=run_id,
            workspace_roots=workspace_roots,
        )
        self._roots_by_run[(task_id, run_id)] = roots
        return LocalExecutionSandbox(task_id=task_id, run_id=run_id, roots=roots)

    def materialize_artifact_path(
        self,
        *,
        task_id: str,
        run_id: str,
        sandbox_path: str,
    ) -> tuple[str, Path, str]:
        roots = self._roots_by_run.get((task_id, run_id))
        if roots is None:
            raise KeyError(f"unknown sandbox roots for task/run: {task_id}/{run_id}")
        normalized = normalize_sandbox_path(sandbox_path)
        resolved = _resolve_host_path(roots, normalized)
        if not resolved.is_file():
            raise ValueError(f"artifact path is not a file: {normalized.logical_path}")
        return (
            _artifact_logical_path(normalized),
            resolved,
            _default_persistence_class(normalized.zone),
        )


class LocalExecutionSandbox:
    def __init__(self, *, task_id: str, run_id: str, roots: SandboxRoots) -> None:
        self._task_id = task_id
        self._run_id = run_id
        self._roots = roots
        self._executor = CommandExecutor()

    def get_workspace_root(self) -> str:
        return str(self._roots.workspace_root)

    def get_scratch_root(self) -> str:
        return str(self._roots.scratch_root)

    def get_memory_root(self) -> str:
        return str(self._roots.memory_root)

    def normalize_path(self, path: str) -> str:
        return normalize_sandbox_path(path).logical_path

    def read_text(self, path: str) -> str:
        resolved = self._resolve(path)
        return resolved.read_text(encoding="utf-8")

    def write_text(self, path: str, content: str) -> None:
        resolved = self._resolve(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def list_files(self, root: str) -> list[str]:
        normalized = normalize_sandbox_path(root)
        resolved_root = _resolve_host_path(self._roots, normalized)
        if resolved_root.is_file():
            return [normalized.logical_path]
        if not resolved_root.exists():
            return []
        files: list[str] = []
        for candidate in sorted(path for path in resolved_root.rglob("*") if path.is_file()):
            relative = candidate.relative_to(resolved_root)
            if normalized.logical_path == normalized.zone:
                suffix = relative.as_posix()
                files.append(normalized.zone if not suffix else f"{normalized.zone}/{suffix}")
            else:
                base = normalized.logical_path
                suffix = relative.as_posix()
                files.append(base if not suffix else f"{base}/{suffix}")
        return files

    def execute_command(self, command: list[str], cwd: str | None = None) -> CommandResult:
        normalized = normalize_sandbox_path(cwd or ZONE_WORKSPACE)
        resolved_cwd = _resolve_host_path(self._roots, normalized)
        if normalized.zone == ZONE_WORKSPACE:
            resolved_cwd = _ensure_allowed_workspace_root(self._roots, resolved_cwd)
        return self._executor.execute(command, resolved_cwd)

    def _resolve(self, path: str) -> Path:
        normalized = normalize_sandbox_path(path)
        return _resolve_host_path(self._roots, normalized)


def _resolve_host_path(roots: SandboxRoots, normalized: NormalizedSandboxPath) -> Path:
    if normalized.zone == ZONE_WORKSPACE:
        base_root = roots.workspace_root
    elif normalized.zone == ZONE_SCRATCH:
        base_root = roots.scratch_root
    elif normalized.zone == ZONE_MEMORY:
        base_root = roots.memory_root
    else:  # pragma: no cover
        raise ValueError(f"unsupported sandbox zone: {normalized.zone}")
    candidate = base_root / normalized.relative_path
    return ensure_within_root(base_root, candidate)


def _ensure_allowed_workspace_root(roots: SandboxRoots, candidate: Path) -> Path:
    for allowed_root in roots.allowed_workspace_roots:
        try:
            return ensure_within_root(allowed_root, candidate)
        except ValueError:
            continue
    raise ValueError("command cwd must resolve inside a governed workspace root")


def _default_persistence_class(zone: str) -> str:
    if zone == ZONE_MEMORY:
        return "project"
    if zone == ZONE_SCRATCH:
        return "ephemeral"
    return "run"


def _artifact_logical_path(normalized: NormalizedSandboxPath) -> str:
    if normalized.zone == ZONE_WORKSPACE:
        relative = normalized.relative_path.as_posix()
        return relative if relative != "." else ""
    return normalized.logical_path
