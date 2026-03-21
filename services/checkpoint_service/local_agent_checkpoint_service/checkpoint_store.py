from __future__ import annotations

import sqlite3
from typing import Protocol
from uuid import uuid4

from services.checkpoint_service.local_agent_checkpoint_service.checkpoint_models import (
    CheckpointMetadata,
    ResumeHandle,
)
from services.checkpoint_service.local_agent_checkpoint_service.thread_registry import (
    ThreadRegistry,
)


class CheckpointStore(Protocol):
    def create_thread(self, task_id: str, run_id: str) -> str: ...

    def save_metadata(self, metadata: CheckpointMetadata) -> None: ...

    def list_checkpoints(self, task_id: str, run_id: str) -> list[CheckpointMetadata]: ...

    def get_resume_handle(self, task_id: str, run_id: str) -> ResumeHandle | None: ...

    def bind_runtime_thread(self, task_id: str, run_id: str, thread_id: str) -> None: ...

    def save_thread_state(self, thread_id: str, state: bytes) -> None: ...

    def load_thread_state(self, thread_id: str) -> bytes | None: ...


class SQLiteCheckpointStore:
    def __init__(self, database_path: str, *, thread_registry: ThreadRegistry) -> None:
        self._database_path = database_path
        self._thread_registry = thread_registry
        self._ensure_schema()

    def create_thread(self, task_id: str, run_id: str) -> str:
        thread_id = f"thread_{uuid4().hex}"
        self.bind_runtime_thread(task_id, run_id, thread_id)
        return thread_id

    def save_metadata(self, metadata: CheckpointMetadata) -> None:
        self.bind_runtime_thread(metadata.task_id, metadata.run_id, metadata.thread_id)
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO checkpoint_metadata(
                    checkpoint_id,
                    task_id,
                    run_id,
                    thread_id,
                    checkpoint_index,
                    created_at,
                    reason
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.checkpoint_id,
                    metadata.task_id,
                    metadata.run_id,
                    metadata.thread_id,
                    metadata.checkpoint_index,
                    metadata.created_at,
                    metadata.reason,
                ),
            )
            connection.commit()

    def list_checkpoints(self, task_id: str, run_id: str) -> list[CheckpointMetadata]:
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT checkpoint_id, task_id, run_id, thread_id, checkpoint_index, created_at, reason
                FROM checkpoint_metadata
                WHERE task_id = ? AND run_id = ?
                ORDER BY checkpoint_index ASC, created_at ASC
                """,
                (task_id, run_id),
            ).fetchall()
        return [
            CheckpointMetadata(
                checkpoint_id=str(row[0]),
                task_id=str(row[1]),
                run_id=str(row[2]),
                thread_id=str(row[3]),
                checkpoint_index=int(row[4]),
                created_at=str(row[5]),
                reason=str(row[6]) if row[6] is not None else None,
            )
            for row in rows
        ]

    def get_resume_handle(self, task_id: str, run_id: str) -> ResumeHandle | None:
        thread_id = self._thread_registry.get_thread_id(task_id, run_id)
        if thread_id is None:
            return None
        checkpoints = self.list_checkpoints(task_id, run_id)
        latest_checkpoint = checkpoints[-1] if checkpoints else None
        return ResumeHandle(
            task_id=task_id,
            run_id=run_id,
            thread_id=thread_id,
            latest_checkpoint_id=latest_checkpoint.checkpoint_id if latest_checkpoint else None,
            latest_checkpoint_reason=latest_checkpoint.reason if latest_checkpoint else None,
        )

    def bind_runtime_thread(self, task_id: str, run_id: str, thread_id: str) -> None:
        self._thread_registry.bind_thread(task_id, run_id, thread_id)

    def save_thread_state(self, thread_id: str, state: bytes) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO checkpoint_thread_state(thread_id, state)
                VALUES(?, ?)
                ON CONFLICT(thread_id)
                DO UPDATE SET state = excluded.state
                """,
                (thread_id, sqlite3.Binary(state)),
            )
            connection.commit()

    def load_thread_state(self, thread_id: str) -> bytes | None:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT state
                FROM checkpoint_thread_state
                WHERE thread_id = ?
                """,
                (thread_id,),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return bytes(row[0])

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoint_metadata(
                    checkpoint_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    checkpoint_index INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    reason TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoint_thread_state(
                    thread_id TEXT PRIMARY KEY,
                    state BLOB NOT NULL
                )
                """
            )
            connection.commit()
