from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ZONE_WORKSPACE = "workspace"
ZONE_SCRATCH = "scratch"
ZONE_MEMORY = "memory"
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
                return "/"
            return f"/{self.relative_path.as_posix()}"
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

    if logical_path == SCRATCH_MOUNT or _is_relative_to(logical_path, SCRATCH_MOUNT):
        zone = ZONE_SCRATCH
        relative_path = logical_path.relative_to(SCRATCH_MOUNT)
    elif logical_path == MEMORY_MOUNT or _is_relative_to(logical_path, MEMORY_MOUNT):
        zone = ZONE_MEMORY
        relative_path = logical_path.relative_to(MEMORY_MOUNT)
    else:
        zone = ZONE_WORKSPACE
        relative_path = logical_path.relative_to(PurePosixPath("/"))

    relative_path = relative_path if relative_path != PurePosixPath(".") else PurePosixPath(".")
    return NormalizedSandboxPath(zone=zone, relative_path=relative_path)


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
