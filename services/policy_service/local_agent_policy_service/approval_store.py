from __future__ import annotations

import json
import sqlite3
from typing import Protocol, cast

from services.policy_service.local_agent_policy_service.policy_models import (
    ApprovalRequest,
    ApprovalStatus,
)


class ApprovalStore(Protocol):
    def create_request(self, request: ApprovalRequest) -> None: ...

    def get_request(self, approval_id: str) -> ApprovalRequest | None: ...

    def list_for_task(self, task_id: str, run_id: str | None = None) -> list[ApprovalRequest]: ...

    def decide(self, approval_id: str, decision: str, decided_at: str) -> ApprovalRequest: ...


class SQLiteApprovalStore:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._ensure_schema()

    def create_request(self, request: ApprovalRequest) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO approval_requests(
                    approval_id,
                    task_id,
                    run_id,
                    type,
                    scope,
                    description,
                    created_at,
                    status,
                    decision,
                    decided_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.approval_id,
                    request.task_id,
                    request.run_id,
                    request.type,
                    json.dumps(request.scope, sort_keys=True),
                    request.description,
                    request.created_at,
                    request.status,
                    request.decision,
                    request.decided_at,
                ),
            )
            connection.commit()

    def get_request(self, approval_id: str) -> ApprovalRequest | None:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT approval_id, task_id, run_id, type, scope, description,
                       created_at, status, decision, decided_at
                FROM approval_requests
                WHERE approval_id = ?
                """,
                (approval_id,),
            ).fetchone()
        return _row_to_approval(row)

    def list_for_task(self, task_id: str, run_id: str | None = None) -> list[ApprovalRequest]:
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT approval_id, task_id, run_id, type, scope, description,
                       created_at, status, decision, decided_at
                FROM approval_requests
                WHERE task_id = ?
                  AND (? IS NULL OR run_id = ?)
                ORDER BY created_at ASC, approval_id ASC
                """,
                (task_id, run_id, run_id),
            ).fetchall()
        return [cast(ApprovalRequest, _row_to_approval(row)) for row in rows if row is not None]

    def decide(self, approval_id: str, decision: str, decided_at: str) -> ApprovalRequest:
        request = self.get_request(approval_id)
        if request is None:
            raise KeyError(f"unknown approval: {approval_id}")
        if request.status != "pending":
            raise ValueError(f"approval {approval_id} is already {request.status}")
        if decision not in {"approved", "rejected"}:
            raise ValueError("approval decision must be approved or rejected")
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                UPDATE approval_requests
                SET decision = ?, decided_at = ?, status = ?
                WHERE approval_id = ?
                """,
                (decision, decided_at, decision, approval_id),
            )
            connection.commit()
        request = self.get_request(approval_id)
        if request is None:
            raise KeyError(f"unknown approval: {approval_id}")
        return request

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_requests(
                    approval_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decision TEXT,
                    decided_at TEXT
                )
                """
            )
            connection.commit()


def _row_to_approval(row: sqlite3.Row | tuple | None) -> ApprovalRequest | None:
    if row is None:
        return None
    return ApprovalRequest(
        approval_id=str(row[0]),
        task_id=str(row[1]),
        run_id=str(row[2]),
        type=str(row[3]),
        scope=json.loads(str(row[4])),
        description=str(row[5]),
        created_at=str(row[6]),
        status=_approval_status(row[7]),
        decision=_optional_approval_status(row[8]),
        decided_at=str(row[9]) if row[9] is not None else None,
    )


def _approval_status(value: object) -> ApprovalStatus:
    normalized = str(value)
    if normalized not in {"pending", "approved", "rejected"}:
        raise ValueError(f"invalid approval status: {normalized}")
    return cast(ApprovalStatus, normalized)


def _optional_approval_status(value: object) -> ApprovalStatus | None:
    if value is None:
        return None
    return _approval_status(value)
