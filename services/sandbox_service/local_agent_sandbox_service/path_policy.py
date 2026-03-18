from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ZONE_WORKSPACE = "workspace"
ZONE_SCRATCH = "scratch"
ZONE_MEMORY = "memory"
WORKSPACE_MOUNT = PurePosixPath("/workspace")
SCRATCH_MOUNT = PurePosixPath("/tmp")
MEMORY_MOUNT = PurePosixPath("/.memory")


@dataclass(frozen=True, slots=True)
class NormalizedSandboxPath:
    zone: str
    relative_path: PurePosixPath

    @property
    def logical_path(self) -> str:
        if self.zone == ZONE_WORKSPACE:
            if self.relative_path == PurePosixPath("."):
                return WORKSPACE_MOUNT.as_posix()
            return f"{WORKSPACE_MOUNT.as_posix()}/{self.relative_path.as_posix()}"
        mount = SCRATCH_MOUNT if self.zone == ZONE_SCRATCH else MEMORY_MOUNT
        if self.relative_path == PurePosixPath("."):
            return mount.as_posix()
        return f"{mount.as_posix()}/{self.relative_path.as_posix()}"


def normalize_sandbox_path(path: str) -> NormalizedSandboxPath:
    raw = str(path).strip()
    if not raw:
        raise ValueError("sandbox path must be a non-empty string")
    if not raw.startswith("/"):
        raise ValueError("sandbox path must be an absolute virtual path")
    logical_path = PurePosixPath(raw)
    for part in logical_path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError("sandbox path cannot traverse outside its virtual root")

    if logical_path == WORKSPACE_MOUNT or _is_relative_to(logical_path, WORKSPACE_MOUNT):
        zone = ZONE_WORKSPACE
        relative_path = logical_path.relative_to(WORKSPACE_MOUNT)
    elif logical_path == SCRATCH_MOUNT or _is_relative_to(logical_path, SCRATCH_MOUNT):
        zone = ZONE_SCRATCH
        relative_path = logical_path.relative_to(SCRATCH_MOUNT)
    elif logical_path == MEMORY_MOUNT or _is_relative_to(logical_path, MEMORY_MOUNT):
        zone = ZONE_MEMORY
        relative_path = logical_path.relative_to(MEMORY_MOUNT)
    else:
        raise ValueError("sandbox path must be under /workspace, /tmp, or /.memory")

    relative_path = relative_path if relative_path != PurePosixPath(".") else PurePosixPath(".")
    return NormalizedSandboxPath(zone=zone, relative_path=relative_path)


def normalize_workspace_virtual_root(path: str) -> str:
    normalized = normalize_sandbox_path(path)
    if normalized.zone != ZONE_WORKSPACE:
        raise ValueError("virtual workspace root must be under /workspace")
    return normalized.logical_path


def _is_relative_to(path: PurePosixPath, root: PurePosixPath) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def ensure_within_root(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("resolved path escapes governed sandbox root") from exc
    return resolved_candidate
