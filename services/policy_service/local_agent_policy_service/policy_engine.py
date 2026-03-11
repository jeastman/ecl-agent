from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from services.policy_service.local_agent_policy_service.boundary_scope import (
    BoundaryGrantStore,
    describe_boundary,
)
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


@dataclass(slots=True)
class RuntimePolicyEngine:
    policy_config: dict[str, object]
    boundary_grants: BoundaryGrantStore | None = None

    def evaluate(self, context: OperationContext) -> PolicyDecision:
        if self._is_denied(context):
            return PolicyDecision(
                decision="DENY",
                reason=self._deny_reason(context),
            )

        boundary = describe_boundary(context)
        if boundary is not None and self.boundary_grants is not None:
            if self.boundary_grants.has_grant(
                context.task_id,
                context.run_id,
                boundary.boundary_key,
            ):
                return PolicyDecision(
                    decision="ALLOW",
                    reason="Run-scoped boundary grant already exists.",
                    boundary_key=boundary.boundary_key,
                    approval_scope=boundary.scope,
                )

        if self._requires_approval(context):
            if boundary is None:
                return PolicyDecision(
                    decision="DENY",
                    reason="Operation requires approval but no stable approval boundary could be derived.",
                )
            return PolicyDecision(
                decision="REQUIRE_APPROVAL",
                reason=boundary.description,
                boundary_key=boundary.boundary_key,
                approval_scope=boundary.scope,
            )

        return PolicyDecision(
            decision="ALLOW",
            reason="Operation falls within the default low-risk policy tier.",
            boundary_key=boundary.boundary_key if boundary is not None else None,
            approval_scope=boundary.scope if boundary is not None else None,
        )

    def _requires_approval(self, context: OperationContext) -> bool:
        if context.operation_type == "file.write":
            path_scope = context.path_scope or ""
            return path_scope.startswith("workspace/") and not path_scope.startswith(
                "workspace/artifacts/"
            )

        if context.operation_type == "command.execute":
            return (context.command_class or "unknown") not in _safe_command_classes(
                self.policy_config
            )

        if context.operation_type == "memory.write":
            return context.memory_scope == "project"

        return False

    def _is_denied(self, context: OperationContext) -> bool:
        if context.operation_type == "file.write":
            path_scope = context.path_scope or ""
            return path_scope.startswith("memory/identity/")

        if context.operation_type == "command.execute":
            command_class = context.command_class or "unknown"
            return command_class in _deny_command_classes(self.policy_config)

        if context.operation_type == "memory.write":
            if context.memory_scope == "identity":
                return True
            if context.memory_scope == "project" and (context.namespace or "").startswith(
                "identity."
            ):
                return True

        return False

    def _deny_reason(self, context: OperationContext) -> str:
        if context.operation_type == "command.execute":
            command_class = context.command_class or "unknown"
            if command_class == "network":
                return "External network access is denied by the runtime policy."
            if command_class == "destructive":
                return "Destructive command classes are denied by the runtime policy."
            return f"Command class {command_class} is denied by the runtime policy."
        if context.operation_type == "memory.write":
            return "Identity memory mutation is denied by the runtime policy."
        return "Operation is denied by the runtime policy."


def _safe_command_classes(policy_config: dict[str, object]) -> set[str]:
    configured = policy_config.get("safe_command_classes")
    if isinstance(configured, list) and all(isinstance(item, str) for item in configured):
        return {item for item in configured if item}
    return {"safe_read", "safe_exec"}


def _deny_command_classes(policy_config: dict[str, object]) -> set[str]:
    configured = policy_config.get("deny_command_classes")
    if isinstance(configured, list) and all(isinstance(item, str) for item in configured):
        return {item for item in configured if item}
    return {"destructive", "network", "secrets"}
