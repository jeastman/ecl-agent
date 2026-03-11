from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

PolicyDecisionKind = Literal["ALLOW", "REQUIRE_APPROVAL", "DENY"]


@dataclass(slots=True)
class OperationContext:
    task_id: str
    run_id: str
    operation_type: str
    path_scope: str | None = None
    command_class: str | None = None
    memory_scope: str | None = None
    namespace: str | None = None
    agent_role: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PolicyDecision:
    decision: PolicyDecisionKind
    reason: str
    boundary_key: str | None = None
    approval_scope: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ApprovalRequest:
    approval_id: str
    task_id: str
    run_id: str
    type: str
    scope: dict[str, Any]
    description: str
    created_at: str
    status: str
    decision: str | None = None
    decided_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
