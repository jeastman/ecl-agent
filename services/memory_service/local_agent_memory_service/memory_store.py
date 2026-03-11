from __future__ import annotations

import json
import sqlite3
from typing import Protocol

from services.memory_service.local_agent_memory_service.memory_models import MemoryRecord


class MemoryStore(Protocol):
    def write_memory(self, record: MemoryRecord) -> None: ...

    def read_memory(self, memory_id: str) -> MemoryRecord | None: ...

    def list_memory(
        self,
        scope: str | None = None,
        namespace: str | None = None,
    ) -> list[MemoryRecord]: ...

    def delete_memory(self, memory_id: str) -> None: ...


class SQLiteMemoryStore:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._ensure_schema()

    def write_memory(self, record: MemoryRecord) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO memory_records(
                    memory_id,
                    scope,
                    namespace,
                    content,
                    summary,
                    provenance,
                    created_at,
                    updated_at,
                    source_run,
                    confidence
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id)
                DO UPDATE SET
                    scope = excluded.scope,
                    namespace = excluded.namespace,
                    content = excluded.content,
                    summary = excluded.summary,
                    provenance = excluded.provenance,
                    updated_at = excluded.updated_at,
                    source_run = excluded.source_run,
                    confidence = excluded.confidence
                """,
                (
                    record.memory_id,
                    record.scope,
                    record.namespace,
                    record.content,
                    record.summary,
                    json.dumps(record.provenance, sort_keys=True),
                    record.created_at,
                    record.updated_at,
                    record.source_run,
                    record.confidence,
                ),
            )
            connection.commit()

    def read_memory(self, memory_id: str) -> MemoryRecord | None:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT memory_id, scope, namespace, content, summary, provenance,
                       created_at, updated_at, source_run, confidence
                FROM memory_records
                WHERE memory_id = ?
                """,
                (memory_id,),
            ).fetchone()
        return _row_to_memory(row)

    def list_memory(
        self,
        scope: str | None = None,
        namespace: str | None = None,
    ) -> list[MemoryRecord]:
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT memory_id, scope, namespace, content, summary, provenance,
                       created_at, updated_at, source_run, confidence
                FROM memory_records
                WHERE (? IS NULL OR scope = ?)
                  AND (? IS NULL OR namespace = ?)
                ORDER BY created_at ASC, memory_id ASC
                """,
                (scope, scope, namespace, namespace),
            ).fetchall()
        return [_row_to_memory(row) for row in rows if row is not None]

    def delete_memory(self, memory_id: str) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("DELETE FROM memory_records WHERE memory_id = ?", (memory_id,))
            connection.commit()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_records(
                    memory_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source_run TEXT,
                    confidence REAL
                )
                """
            )
            connection.commit()


def _row_to_memory(row: sqlite3.Row | tuple | None) -> MemoryRecord | None:
    if row is None:
        return None
    return MemoryRecord(
        memory_id=str(row[0]),
        scope=str(row[1]),
        namespace=str(row[2]),
        content=str(row[3]),
        summary=str(row[4]),
        provenance=json.loads(str(row[5])),
        created_at=str(row[6]),
        updated_at=str(row[7]),
        source_run=str(row[8]) if row[8] is not None else None,
        confidence=float(row[9]) if row[9] is not None else None,
    )
