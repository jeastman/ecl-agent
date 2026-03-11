from __future__ import annotations

import json
import sqlite3
from typing import Any, Protocol
from uuid import uuid4

from packages.protocol.local_agent_protocol.models import utc_now_timestamp
from services.observability_service.local_agent_observability_service.observability_models import (
    DiagnosticRecord,
)


class DiagnosticStore(Protocol):
    def append_diagnostic(
        self,
        *,
        task_id: str,
        run_id: str,
        kind: str,
        message: str,
        details: dict[str, Any],
    ) -> None: ...

    def list_diagnostics(
        self,
        task_id: str,
        run_id: str | None = None,
    ) -> list[DiagnosticRecord]: ...


class SQLiteDiagnosticStore:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._ensure_schema()

    def append_diagnostic(
        self,
        *,
        task_id: str,
        run_id: str,
        kind: str,
        message: str,
        details: dict[str, Any],
    ) -> None:
        record = DiagnosticRecord(
            diagnostic_id=f"diag_{uuid4().hex}",
            task_id=task_id,
            run_id=run_id,
            kind=kind,
            message=message,
            created_at=utc_now_timestamp(),
            details=details,
        )
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO diagnostics(
                    diagnostic_id,
                    task_id,
                    run_id,
                    kind,
                    message,
                    created_at,
                    details
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.diagnostic_id,
                    record.task_id,
                    record.run_id,
                    record.kind,
                    record.message,
                    record.created_at,
                    json.dumps(record.details, sort_keys=True),
                ),
            )
            connection.commit()

    def list_diagnostics(
        self,
        task_id: str,
        run_id: str | None = None,
    ) -> list[DiagnosticRecord]:
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT diagnostic_id, task_id, run_id, kind, message, created_at, details
                FROM diagnostics
                WHERE task_id = ?
                  AND (? IS NULL OR run_id = ?)
                ORDER BY created_at ASC, diagnostic_id ASC
                """,
                (task_id, run_id, run_id),
            ).fetchall()
        return [
            DiagnosticRecord(
                diagnostic_id=str(row[0]),
                task_id=str(row[1]),
                run_id=str(row[2]),
                kind=str(row[3]),
                message=str(row[4]),
                created_at=str(row[5]),
                details=json.loads(str(row[6])),
            )
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS diagnostics(
                    diagnostic_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    details TEXT NOT NULL
                )
                """
            )
            connection.commit()
