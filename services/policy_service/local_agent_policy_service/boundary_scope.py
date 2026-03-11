from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Protocol

from services.policy_service.local_agent_policy_service.policy_models import OperationContext


@dataclass(slots=True)
class BoundaryGrant:
    task_id: str
    run_id: str
    boundary_key: str
    approval_id: str
    granted_at: str


class BoundaryGrantStore(Protocol):
    def has_grant(self, task_id: str, run_id: str, boundary_key: str) -> bool: ...

    def grant(self, grant: BoundaryGrant) -> None: ...


class SQLiteBoundaryGrantStore:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._ensure_schema()

    def has_grant(self, task_id: str, run_id: str, boundary_key: str) -> bool:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM boundary_grants
                WHERE task_id = ? AND run_id = ? AND boundary_key = ?
                """,
                (task_id, run_id, boundary_key),
            ).fetchone()
        return row is not None

    def grant(self, grant: BoundaryGrant) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO boundary_grants(task_id, run_id, boundary_key, approval_id, granted_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(task_id, run_id, boundary_key)
                DO UPDATE SET
                    approval_id = excluded.approval_id,
                    granted_at = excluded.granted_at
                """,
                (
                    grant.task_id,
                    grant.run_id,
                    grant.boundary_key,
                    grant.approval_id,
                    grant.granted_at,
                ),
            )
            connection.commit()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS boundary_grants(
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    boundary_key TEXT NOT NULL,
                    approval_id TEXT NOT NULL,
                    granted_at TEXT NOT NULL,
                    PRIMARY KEY(task_id, run_id, boundary_key)
                )
                """
            )
            connection.commit()


@dataclass(slots=True)
class BoundaryDescriptor:
    boundary_key: str
    scope: dict[str, str]
    description: str


def describe_boundary(context: OperationContext) -> BoundaryDescriptor | None:
    if context.operation_type == "file.write" and context.path_scope is not None:
        if context.path_scope.startswith("workspace/artifacts/"):
            return None
        if context.path_scope.startswith("scratch/"):
            return None
        if context.path_scope.startswith("workspace/"):
            subtree = _workspace_subtree(context.path_scope)
            return BoundaryDescriptor(
                boundary_key=f"file.write:{subtree}",
                scope={"kind": "file.write", "path": subtree},
                description=f"Allow writes to {subtree} for this run",
            )
        return BoundaryDescriptor(
            boundary_key=f"file.write:{context.path_scope}",
            scope={"kind": "file.write", "path": context.path_scope},
            description=f"Allow writes to {context.path_scope} for this run",
        )

    if context.operation_type == "command.execute":
        command_class = context.command_class or "unknown"
        cwd = context.path_scope or "workspace"
        return BoundaryDescriptor(
            boundary_key=f"command.execute:{command_class}:{cwd}",
            scope={"kind": "command.execute", "command_class": command_class, "cwd": cwd},
            description=f"Allow {command_class} commands in {cwd} for this run",
        )

    if context.operation_type == "memory.write" and context.memory_scope == "project":
        namespace = context.namespace or "project.default"
        return BoundaryDescriptor(
            boundary_key=f"memory.write:project:{namespace}",
            scope={"kind": "memory.write", "scope": "project", "namespace": namespace},
            description=f"Allow durable memory writes in namespace {namespace} for this run",
        )
    if context.operation_type == "skill.install":
        metadata = context.metadata or {}
        target_scope = str(metadata.get("target_scope") or "primary_agent")
        target_role = str(metadata.get("target_role") or "") or None
        install_mode = str(metadata.get("install_mode") or "fail_if_exists")
        skill_id = str(metadata.get("skill_id") or "unknown")
        scope = {
            "kind": "skill.install",
            "target_scope": target_scope,
            "install_mode": install_mode,
            "skill_id": skill_id,
        }
        boundary_key = (
            f"skill.install:{target_scope}:{target_role or 'primary'}:{skill_id}:{install_mode}"
        )
        if target_role is not None:
            scope["target_role"] = target_role
        return BoundaryDescriptor(
            boundary_key=boundary_key,
            scope=scope,
            description=f"Allow {install_mode} installation for skill {skill_id}",
        )
    return None


def _workspace_subtree(path_scope: str) -> str:
    parts = [part for part in path_scope.split("/") if part]
    if len(parts) <= 2:
        return "workspace/**"
    if len(parts) == 3:
        return f"{'/'.join(parts[:2])}/**"
    return f"{'/'.join(parts[:3])}/**"
