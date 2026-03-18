from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import PurePosixPath
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
            return (
                path_scope.startswith("/")
                and not path_scope.startswith("/workspace/artifacts/")
                and not (path_scope == "/tmp" or path_scope.startswith("/tmp/"))
                and not (path_scope == "/.memory" or path_scope.startswith("/.memory/"))
            )

        if context.operation_type == "command.execute":
            if _is_scratch_only_destructive_command(context):
                return False
            return (context.command_class or "unknown") not in _safe_command_classes(
                self.policy_config
            )

        if context.operation_type == "memory.write":
            return context.memory_scope == "project"

        if context.operation_type == "skill.install":
            metadata = context.metadata or {}
            return (
                bool(metadata.get("has_scripts"))
                or bool(metadata.get("overwrite"))
                or (metadata.get("install_mode") == "replace")
            )
        if context.operation_type in {"web.fetch", "web.search"}:
            return _web_access_mode(self.policy_config) == "require_approval"

        return False

    def _is_denied(self, context: OperationContext) -> bool:
        if context.operation_type == "file.write":
            path_scope = context.path_scope or ""
            return path_scope.startswith("/.memory/identity/")

        if context.operation_type == "command.execute":
            command_class = context.command_class or "unknown"
            if command_class == "destructive" and _is_scratch_only_destructive_command(context):
                return False
            return command_class in _deny_command_classes(self.policy_config)

        if context.operation_type == "memory.write":
            if context.memory_scope == "identity":
                return True
            if context.memory_scope == "project" and (context.namespace or "").startswith(
                "identity."
            ):
                return True
        if context.operation_type == "skill.install":
            path_scope = context.path_scope or ""
            return ".." in path_scope
        if context.operation_type in {"web.fetch", "web.search"}:
            return _web_access_mode(self.policy_config) == "deny"

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
        if context.operation_type == "skill.install":
            return "Skill installation target is denied by the runtime policy."
        if context.operation_type in {"web.fetch", "web.search"}:
            return "Outbound web access is denied by the runtime policy."
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


def _web_access_mode(policy_config: dict[str, object]) -> str:
    configured = policy_config.get("web_access_mode", "allow")
    if not isinstance(configured, str):
        return "allow"
    normalized = configured.strip().lower()
    if normalized in {"allow", "require_approval", "deny"}:
        return normalized
    return "allow"


def _is_scratch_only_destructive_command(context: OperationContext) -> bool:
    if (context.command_class or "unknown") != "destructive":
        return False
    metadata = context.metadata or {}
    command = metadata.get("command")
    if not isinstance(command, list) or not all(isinstance(part, str) and part for part in command):
        return False
    head = command[0].rsplit("/", 1)[-1]
    if head != "rm":
        return False
    targets = _extract_rm_targets(command[1:])
    if not targets:
        return False
    cwd = context.path_scope or "/"
    return all(_is_virtual_scratch_path(_resolve_command_target_path(target, cwd)) for target in targets)


def _extract_rm_targets(arguments: list[str]) -> list[str]:
    targets: list[str] = []
    literal_mode = False
    for argument in arguments:
        if not argument:
            continue
        if literal_mode:
            targets.append(argument)
            continue
        if argument == "--":
            literal_mode = True
            continue
        if argument.startswith("-"):
            continue
        targets.append(argument)
    return targets


def _resolve_command_target_path(target: str, cwd: str) -> str:
    if target.startswith("/"):
        return posixpath.normpath(target)
    base = cwd if cwd.startswith("/") else "/"
    return posixpath.normpath(PurePosixPath(base).joinpath(target).as_posix())


def _is_virtual_scratch_path(path: str) -> bool:
    return path == "/tmp" or path.startswith("/tmp/")
