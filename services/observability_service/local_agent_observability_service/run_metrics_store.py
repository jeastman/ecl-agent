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
                    started_at,
                    ended_at,
                    event_count,
                    artifact_count,
                    checkpoint_count,
                    approval_count,
                    resume_count,
                    deny_count,
                    last_updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id, run_id)
                DO UPDATE SET
                    started_at = excluded.started_at,
                    ended_at = excluded.ended_at,
                    event_count = excluded.event_count,
                    artifact_count = excluded.artifact_count,
                    checkpoint_count = excluded.checkpoint_count,
                    approval_count = excluded.approval_count,
                    resume_count = excluded.resume_count,
                    deny_count = excluded.deny_count,
                    last_updated_at = excluded.last_updated_at
                """,
                (
                    record.task_id,
                    record.run_id,
                    record.started_at,
                    record.ended_at,
                    record.event_count,
                    record.artifact_count,
                    record.checkpoint_count,
                    record.approval_count,
                    record.resume_count,
                    record.deny_count,
                    record.last_updated_at,
                ),
            )
            connection.commit()

    def read_metrics(self, task_id: str, run_id: str) -> RunMetricsRecord | None:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT task_id, run_id, started_at, ended_at, event_count, artifact_count,
                       checkpoint_count, approval_count, resume_count, deny_count, last_updated_at
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
            started_at=str(row[2]) if row[2] is not None else None,
            ended_at=str(row[3]) if row[3] is not None else None,
            event_count=int(row[4]),
            artifact_count=int(row[5]),
            checkpoint_count=int(row[6]),
            approval_count=int(row[7]),
            resume_count=int(row[8]),
            deny_count=int(row[9]),
            last_updated_at=str(row[10]) if row[10] is not None else None,
        )

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_metrics(
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    event_count INTEGER NOT NULL DEFAULT 0,
                    artifact_count INTEGER NOT NULL DEFAULT 0,
                    checkpoint_count INTEGER NOT NULL,
                    approval_count INTEGER NOT NULL,
                    resume_count INTEGER NOT NULL,
                    deny_count INTEGER NOT NULL DEFAULT 0,
                    last_updated_at TEXT,
                    PRIMARY KEY(task_id, run_id)
                )
                """
            )
            existing_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(run_metrics)").fetchall()
            }
            for statement in _schema_migrations(existing_columns):
                connection.execute(statement)
            connection.commit()


def _schema_migrations(existing_columns: set[str]) -> list[str]:
    migrations: list[str] = []
    if "started_at" not in existing_columns:
        migrations.append("ALTER TABLE run_metrics ADD COLUMN started_at TEXT")
    if "ended_at" not in existing_columns:
        migrations.append("ALTER TABLE run_metrics ADD COLUMN ended_at TEXT")
    if "event_count" not in existing_columns:
        migrations.append(
            "ALTER TABLE run_metrics ADD COLUMN event_count INTEGER NOT NULL DEFAULT 0"
        )
    if "artifact_count" not in existing_columns:
        migrations.append(
            "ALTER TABLE run_metrics ADD COLUMN artifact_count INTEGER NOT NULL DEFAULT 0"
        )
    if "deny_count" not in existing_columns:
        migrations.append(
            "ALTER TABLE run_metrics ADD COLUMN deny_count INTEGER NOT NULL DEFAULT 0"
        )
    return migrations
