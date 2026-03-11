from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class PersistedEvent:
    event_id: str
    event_type: str
    timestamp: str
    task_id: str
    run_id: str
    correlation_id: str | None
    source: dict[str, Any]
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DiagnosticRecord:
    diagnostic_id: str
    task_id: str
    run_id: str
    kind: str
    message: str
    created_at: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RunMetricsRecord:
    task_id: str
    run_id: str
    checkpoint_count: int = 0
    approval_count: int = 0
    resume_count: int = 0
    last_updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
