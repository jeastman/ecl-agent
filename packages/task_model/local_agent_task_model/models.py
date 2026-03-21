from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    CHECKPOINT_SAVED = "checkpoint.saved"
    TASK_PAUSED = "task.paused"
    TASK_CANCELLED = "task.cancelled"
    TASK_RESUMED = "task.resumed"
    TASK_USER_INPUT_RECEIVED = "task.user_input_received"
    APPROVAL_REQUESTED = "approval.requested"
    POLICY_DENIED = "policy.denied"
    RECOVERY_DISCOVERED = "recovery.discovered"
    PLAN_UPDATED = "plan.updated"
    SUBAGENT_STARTED = "subagent.started"
    SUBAGENT_COMPLETED = "subagent.completed"
    TOOL_CALLED = "tool.called"
    TOOL_REJECTED = "tool.rejected"
    ARTIFACT_CREATED = "artifact.created"
    MEMORY_UPDATED = "memory.updated"
    SKILL_INSTALL_REQUESTED = "skill.install.requested"
    SKILL_INSTALL_VALIDATED = "skill.install.validated"
    SKILL_INSTALL_APPROVAL_REQUESTED = "skill.install.approval_requested"
    SKILL_INSTALL_COMPLETED = "skill.install.completed"
    SKILL_INSTALL_FAILED = "skill.install.failed"
    CONVERSATION_COMPACTED = "conversation.compacted"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"


class CompactionTrigger(StrEnum):
    THRESHOLD = "threshold"
    OVERFLOW_FALLBACK = "overflow_fallback"
    EXPLICIT_AGENT = "explicit_agent"
    EXPLICIT_CLIENT = "explicit_client"
    RESUME_BOUNDARY = "resume_boundary"


class TaskStatus(StrEnum):
    CREATED = "created"
    ACCEPTED = "accepted"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class TodoStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass(slots=True)
class TodoItem:
    content: str
    status: TodoStatus

    def to_dict(self) -> dict[str, Any]:
        return {"content": self.content, "status": self.status.value}


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
class RemoteMCPActionState:
    action_id: str
    method: str
    title: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RemoteMCPAuthorizationState:
    server_name: str
    provider_id: str
    status: str
    summary: str
    actions: list[RemoteMCPActionState] = field(default_factory=list)


@dataclass(slots=True)
class RecoverableToolRejection(Exception):
    code: str
    message: str
    category: str
    retryable: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True)
class RecoverableToolRejectionThresholdExceeded(Exception):
    threshold: int
    rejection_count: int
    last_rejection: FailureInfo

    @property
    def summary(self) -> str:
        return (
            "Agent exceeded the recoverable tool rejection limit without adapting. "
            f"Last rejection [{self.last_rejection.code or 'unknown'}]: "
            f"{self.last_rejection.message}"
        )

    def __str__(self) -> str:
        return self.summary


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
    allowed_capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    runtime_user_id: str | None = None
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    current_phase: str | None = None
    latest_summary: str | None = None
    active_subagent: str | None = None
    artifact_count: int = 0
    recoverable_rejection_count: int = 0
    last_event_at: str | None = None
    failure: FailureInfo | None = None
    last_recoverable_rejection: FailureInfo | None = None
    remote_mcp_authorizations: list[RemoteMCPAuthorizationState] = field(default_factory=list)
    awaiting_approval: bool = False
    pending_approval_id: str | None = None
    is_resumable: bool = False
    pause_reason: str | None = None
    todos: list[TodoItem] = field(default_factory=list)
    checkpoint_thread_id: str | None = None
    latest_checkpoint_id: str | None = None
    is_compacted: bool = False
    latest_compaction_id: str | None = None
    latest_compaction_trigger: str | None = None
    links: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        if self.failure is not None:
            payload["failure"] = self.failure.to_dict()
        if self.last_recoverable_rejection is not None:
            payload["last_recoverable_rejection"] = self.last_recoverable_rejection.to_dict()
        return payload


def normalize_todos(value: Any) -> list[TodoItem]:
    if not isinstance(value, list):
        return []
    normalized: list[TodoItem] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        status = item.get("status")
        if not isinstance(content, str) or not isinstance(status, str):
            continue
        stripped_content = content.strip()
        stripped_status = status.strip().lower()
        if not stripped_content:
            continue
        try:
            normalized.append(TodoItem(content=stripped_content, status=TodoStatus(stripped_status)))
        except ValueError:
            continue
    return normalized
