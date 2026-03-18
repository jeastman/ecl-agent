from __future__ import annotations

import json
import sqlite3
from typing import Protocol

from services.observability_service.local_agent_observability_service.observability_models import (
    ConversationCompactionRecord,
)


class ConversationCompactionStore(Protocol):
    def append_compaction(self, record: ConversationCompactionRecord) -> None: ...

    def latest_compaction(
        self, task_id: str, run_id: str
    ) -> ConversationCompactionRecord | None: ...


class SQLiteConversationCompactionStore:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._ensure_schema()

    def append_compaction(self, record: ConversationCompactionRecord) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO conversation_compactions(
                    compaction_id,
                    task_id,
                    run_id,
                    trigger,
                    strategy,
                    cutoff_index,
                    summary_content,
                    created_at,
                    provenance,
                    artifact_path
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.compaction_id,
                    record.task_id,
                    record.run_id,
                    record.trigger,
                    record.strategy,
                    record.cutoff_index,
                    record.summary_content,
                    record.created_at,
                    json.dumps(record.provenance, sort_keys=True),
                    record.artifact_path,
                ),
            )
            connection.commit()

    def latest_compaction(
        self, task_id: str, run_id: str
    ) -> ConversationCompactionRecord | None:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT compaction_id, task_id, run_id, trigger, strategy, cutoff_index,
                       summary_content, created_at, provenance, artifact_path
                FROM conversation_compactions
                WHERE task_id = ? AND run_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (task_id, run_id),
            ).fetchone()
        if row is None:
            return None
        return ConversationCompactionRecord(
            compaction_id=str(row[0]),
            task_id=str(row[1]),
            run_id=str(row[2]),
            trigger=str(row[3]),
            strategy=str(row[4]),
            cutoff_index=int(row[5]),
            summary_content=str(row[6]),
            created_at=str(row[7]),
            provenance=json.loads(str(row[8])),
            artifact_path=str(row[9]) if row[9] is not None else None,
        )

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_compactions(
                    compaction_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    cutoff_index INTEGER NOT NULL,
                    summary_content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    artifact_path TEXT
                )
                """
            )
            connection.commit()
