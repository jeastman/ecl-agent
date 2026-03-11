from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class MemoryRecord:
    memory_id: str
    scope: str
    namespace: str
    content: str
    summary: str
    provenance: dict[str, Any]
    created_at: str
    updated_at: str
    source_run: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
