from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class CheckpointMetadata:
    checkpoint_id: str
    task_id: str
    run_id: str
    thread_id: str
    checkpoint_index: int
    created_at: str
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ResumeHandle:
    task_id: str
    run_id: str
    thread_id: str
    latest_checkpoint_id: str | None = None
    latest_checkpoint_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
