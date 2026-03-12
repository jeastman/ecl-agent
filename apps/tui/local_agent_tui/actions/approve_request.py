from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ApprovalUiDecision = Literal["approve", "reject"]


@dataclass(frozen=True, slots=True)
class ApprovalRequestAction:
    task_id: str
    run_id: str
    approval_id: str
    decision: str


def build_approval_request_action(
    *,
    task_id: str,
    run_id: str,
    approval_id: str,
    decision: ApprovalUiDecision,
) -> ApprovalRequestAction:
    protocol_decision = "approved" if decision == "approve" else "rejected"
    return ApprovalRequestAction(
        task_id=task_id,
        run_id=run_id,
        approval_id=approval_id,
        decision=protocol_decision,
    )
