from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ZONE_WORKSPACE = "workspace"
ZONE_SCRATCH = "scratch"
ZONE_MEMORY = "memory"
ALLOWED_ZONES = {ZONE_WORKSPACE, ZONE_SCRATCH, ZONE_MEMORY}


@dataclass(frozen=True, slots=True)
class NormalizedSandboxPath:
    zone: str
    relative_path: PurePosixPath

    @property
    def logical_path(self) -> str:
        if self.relative_path == PurePosixPath("."):
            return self.zone
        return f"{self.zone}/{self.relative_path.as_posix()}"


def normalize_sandbox_path(path: str) -> NormalizedSandboxPath:
    raw = str(path).strip()
    if not raw:
        raise ValueError("sandbox path must be a non-empty string")
    if raw.startswith("/"):
        raise ValueError("sandbox path must be relative to a governed zone")
    parts = PurePosixPath(raw).parts
    if not parts:
        raise ValueError("sandbox path must include a governed zone")
    zone = parts[0]
    if zone not in ALLOWED_ZONES:
        raise ValueError(f"unsupported sandbox zone: {zone}")
    relative_parts = parts[1:]
    for part in relative_parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError("sandbox path cannot traverse outside its zone")
    relative_path = PurePosixPath(*relative_parts) if relative_parts else PurePosixPath(".")
    return NormalizedSandboxPath(zone=zone, relative_path=relative_path)


def ensure_within_root(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("resolved path escapes governed sandbox root") from exc
    return resolved_candidate
