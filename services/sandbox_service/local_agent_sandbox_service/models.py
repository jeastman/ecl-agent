from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    cwd: str
