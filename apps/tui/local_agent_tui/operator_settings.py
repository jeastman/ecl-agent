from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class OperatorSettings:
    runtime_user_id: str | None = None


class OperatorSettingsStore:
    def __init__(self, path: str | None = None) -> None:
        self._path = Path(path).expanduser() if path is not None else _default_path()

    def load(self) -> OperatorSettings:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return OperatorSettings()
        except json.JSONDecodeError:
            return OperatorSettings()
        runtime_user_id = payload.get("runtime_user_id")
        if not isinstance(runtime_user_id, str) or not runtime_user_id.strip():
            return OperatorSettings()
        return OperatorSettings(runtime_user_id=runtime_user_id.strip())

    def save(self, settings: OperatorSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"runtime_user_id": settings.runtime_user_id}, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def _default_path() -> Path:
    return (Path.home() / ".local-agent-harness" / "tui-settings.json").resolve()
