from __future__ import annotations

import sqlite3
from typing import Protocol

from services.observability_service.local_agent_observability_service.observability_models import (
    RunMessageRecord,
)


class RunMessageStore(Protocol):
    def append_message(self, message: RunMessageRecord) -> None: ...

    def list_messages(self, task_id: str, run_id: str) -> list[RunMessageRecord]: ...


class SQLiteRunMessageStore:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._ensure_schema()

    def append_message(self, message: RunMessageRecord) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO run_messages(
                    message_id,
                    task_id,
                    run_id,
                    role,
                    content,
                    created_at
                )
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.task_id,
                    message.run_id,
                    message.role,
                    message.content,
                    message.created_at,
                ),
            )
            connection.commit()

    def list_messages(self, task_id: str, run_id: str) -> list[RunMessageRecord]:
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT message_id, task_id, run_id, role, content, created_at
                FROM run_messages
                WHERE task_id = ? AND run_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (task_id, run_id),
            ).fetchall()
        return [
            RunMessageRecord(
                message_id=str(row[0]),
                task_id=str(row[1]),
                run_id=str(row[2]),
                role=str(row[3]),
                content=str(row[4]),
                created_at=str(row[5]),
            )
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_messages(
                    message_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
