from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_ACCEPTED = "task.accepted"
    TASK_STARTED = "task.started"
    TASK_FAILED = "task.failed"
    TASK_COMPLETED = "task.completed"
    RUNTIME_WARNING = "runtime.warning"


class TaskStatus(StrEnum):
    CREATED = "created"
    ACCEPTED = "accepted"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class ActionDescriptor:
    action: str
    label: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TaskSnapshot:
    task_id: str
    run_id: str
    status: TaskStatus
    objective: str
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    available_actions: list[ActionDescriptor] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload
