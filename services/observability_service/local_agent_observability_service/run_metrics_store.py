from __future__ import annotations

import sqlite3
from typing import Protocol

from services.observability_service.local_agent_observability_service.observability_models import (
    RunMetricsRecord,
)


class RunMetricsStore(Protocol):
    def write_metrics(self, record: RunMetricsRecord) -> None: ...

    def read_metrics(self, task_id: str, run_id: str) -> RunMetricsRecord | None: ...


class SQLiteRunMetricsStore:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._ensure_schema()

    def write_metrics(self, record: RunMetricsRecord) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO run_metrics(
                    task_id,
                    run_id,
                    checkpoint_count,
                    approval_count,
                    resume_count,
                    last_updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id, run_id)
                DO UPDATE SET
                    checkpoint_count = excluded.checkpoint_count,
                    approval_count = excluded.approval_count,
                    resume_count = excluded.resume_count,
                    last_updated_at = excluded.last_updated_at
                """,
                (
                    record.task_id,
                    record.run_id,
                    record.checkpoint_count,
                    record.approval_count,
                    record.resume_count,
                    record.last_updated_at,
                ),
            )
            connection.commit()

    def read_metrics(self, task_id: str, run_id: str) -> RunMetricsRecord | None:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT task_id, run_id, checkpoint_count, approval_count, resume_count, last_updated_at
                FROM run_metrics
                WHERE task_id = ? AND run_id = ?
                """,
                (task_id, run_id),
            ).fetchone()
        if row is None:
            return None
        return RunMetricsRecord(
            task_id=str(row[0]),
            run_id=str(row[1]),
            checkpoint_count=int(row[2]),
            approval_count=int(row[3]),
            resume_count=int(row[4]),
            last_updated_at=str(row[5]) if row[5] is not None else None,
        )

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_metrics(
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    checkpoint_count INTEGER NOT NULL,
                    approval_count INTEGER NOT NULL,
                    resume_count INTEGER NOT NULL,
                    last_updated_at TEXT,
                    PRIMARY KEY(task_id, run_id)
                )
                """
            )
            connection.commit()
