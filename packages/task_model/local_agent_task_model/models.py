from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    PLAN_UPDATED = "plan.updated"
    SUBAGENT_STARTED = "subagent.started"
    TOOL_CALLED = "tool.called"
    ARTIFACT_CREATED = "artifact.created"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"


class TaskStatus(StrEnum):
    CREATED = "created"
    ACCEPTED = "accepted"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class FailureInfo:
    message: str
    code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.code is None:
            payload.pop("code")
        return payload


@dataclass(slots=True)
class RunState:
    task_id: str
    run_id: str
    status: TaskStatus
    objective: str
    created_at: str
    updated_at: str
    accepted_at: str
    workspace_roots: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    current_phase: str | None = None
    latest_summary: str | None = None
    active_subagent: str | None = None
    artifact_count: int = 0
    last_event_at: str | None = None
    failure: FailureInfo | None = None
    links: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        if self.failure is not None:
            payload["failure"] = self.failure.to_dict()
        return payload
