from __future__ import annotations

import subprocess
from pathlib import Path

from services.sandbox_service.local_agent_sandbox_service.models import CommandResult


class CommandExecutor:
    def execute(self, command: list[str], cwd: Path) -> CommandResult:
        if not command or not all(isinstance(part, str) and part for part in command):
            raise ValueError("sandbox command must be a non-empty list of strings")
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
        )
        return CommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            cwd=str(cwd),
        )
