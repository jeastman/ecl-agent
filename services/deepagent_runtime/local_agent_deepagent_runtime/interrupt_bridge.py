from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from services.deepagent_runtime.local_agent_deepagent_runtime.checkpoint_adapter import (
    CheckpointController,
)
from services.policy_service.local_agent_policy_service.policy_models import OperationContext


@dataclass(slots=True)
class ApprovalRequiredInterrupt(Exception):
    approval_id: str
    summary: str


@dataclass(slots=True)
class PolicyDeniedInterrupt(Exception):
    reason: str


@dataclass(slots=True)
class ClarificationRequiredInterrupt(Exception):
    question: str
    reason_code: str | None = None


@dataclass(slots=True)
class CancellationRequestedInterrupt(Exception):
    reason: str | None = None
    checkpoint_id: str | None = None


@dataclass(slots=True)
class InterruptBridge:
    governed_operation: Callable[[OperationContext], None] | None = None
    checkpoint_controller: CheckpointController | None = None
    on_event: Callable[[str, dict[str, Any]], None] | None = None
    cancellation_probe: Callable[[], str | None] | None = None

    def authorize(self, context: OperationContext) -> None:
        self.raise_if_cancelled("cancel_requested")
        if self.governed_operation is None:
            return
        try:
            self.governed_operation(context)
        except ApprovalRequiredInterrupt:
            self._record_interrupt_checkpoint("awaiting_approval")
            raise

    def request_user_input(self, question: str, *, reason_code: str | None = None) -> None:
        self.raise_if_cancelled("cancel_requested")
        self._record_interrupt_checkpoint("awaiting_user_input")
        raise ClarificationRequiredInterrupt(question=question, reason_code=reason_code)

    def raise_if_cancelled(self, reason: str = "cancel_requested") -> None:
        if self.cancellation_probe is None:
            return
        cancel_reason = self.cancellation_probe()
        if cancel_reason is None:
            return
        metadata = self._record_interrupt_checkpoint(reason)
        raise CancellationRequestedInterrupt(
            reason=cancel_reason,
            checkpoint_id=None if metadata is None else metadata.checkpoint_id,
        )

    def _record_interrupt_checkpoint(self, reason: str):
        if self.checkpoint_controller is None:
            return None
        metadata = self.checkpoint_controller.record_checkpoint(reason)
        if self.on_event is not None:
            self.on_event("checkpoint.saved", metadata.to_dict())
        return metadata
