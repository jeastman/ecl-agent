from __future__ import annotations

import sqlite3
from typing import Protocol


class ThreadRegistry(Protocol):
    def bind_thread(self, task_id: str, run_id: str, thread_id: str) -> None: ...

    def get_thread_id(self, task_id: str, run_id: str) -> str | None: ...


class SQLiteThreadRegistry:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._ensure_schema()

    def bind_thread(self, task_id: str, run_id: str, thread_id: str) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO checkpoint_threads(task_id, run_id, thread_id)
                VALUES(?, ?, ?)
                ON CONFLICT(task_id, run_id)
                DO UPDATE SET thread_id = excluded.thread_id
                """,
                (task_id, run_id, thread_id),
            )
            connection.commit()

    def get_thread_id(self, task_id: str, run_id: str) -> str | None:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT thread_id
                FROM checkpoint_threads
                WHERE task_id = ? AND run_id = ?
                """,
                (task_id, run_id),
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoint_threads(
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    PRIMARY KEY(task_id, run_id)
                )
                """
            )
            connection.commit()
