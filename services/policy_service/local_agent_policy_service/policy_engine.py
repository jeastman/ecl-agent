from __future__ import annotations

from typing import Protocol

from services.policy_service.local_agent_policy_service.policy_models import (
    OperationContext,
    PolicyDecision,
)


class PolicyEngine(Protocol):
    def evaluate(self, context: OperationContext) -> PolicyDecision: ...


class PlaceholderPolicyEngine:
    def evaluate(self, context: OperationContext) -> PolicyDecision:
        return PolicyDecision(
            decision="ALLOW",
            reason="Phase 1 placeholder policy engine defers approval behavior.",
        )
