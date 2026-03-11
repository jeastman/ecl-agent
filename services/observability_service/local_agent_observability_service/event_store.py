from __future__ import annotations

import json
import sqlite3
from typing import Protocol

from packages.protocol.local_agent_protocol.models import EventEnvelope
from services.observability_service.local_agent_observability_service.observability_models import (
    PersistedEvent,
)


class EventStore(Protocol):
    def append_event(self, event: EventEnvelope | PersistedEvent) -> None: ...

    def get_events(
        self,
        task_id: str,
        run_id: str | None = None,
        from_event_id: str | None = None,
    ) -> list[PersistedEvent]: ...


class SQLiteEventStore:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._ensure_schema()

    def append_event(self, event: EventEnvelope | PersistedEvent) -> None:
        record = _coerce_event(event)
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO persisted_events(
                    event_id,
                    event_type,
                    timestamp,
                    task_id,
                    run_id,
                    correlation_id,
                    source,
                    payload
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.event_id,
                    record.event_type,
                    record.timestamp,
                    record.task_id,
                    record.run_id,
                    record.correlation_id,
                    json.dumps(record.source, sort_keys=True),
                    json.dumps(record.payload, sort_keys=True),
                ),
            )
            connection.commit()

    def get_events(
        self,
        task_id: str,
        run_id: str | None = None,
        from_event_id: str | None = None,
    ) -> list[PersistedEvent]:
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT event_id, event_type, timestamp, task_id, run_id, correlation_id, source, payload
                FROM persisted_events
                WHERE task_id = ?
                  AND (? IS NULL OR run_id = ?)
                  AND (
                        ? IS NULL OR
                        rowid > COALESCE(
                            (SELECT rowid FROM persisted_events WHERE event_id = ?),
                            0
                        )
                      )
                ORDER BY rowid ASC
                """,
                (task_id, run_id, run_id, from_event_id, from_event_id),
            ).fetchall()
        return [
            PersistedEvent(
                event_id=str(row[0]),
                event_type=str(row[1]),
                timestamp=str(row[2]),
                task_id=str(row[3]),
                run_id=str(row[4]),
                correlation_id=str(row[5]) if row[5] is not None else None,
                source=json.loads(str(row[6])),
                payload=json.loads(str(row[7])),
            )
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS persisted_events(
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    correlation_id TEXT,
                    source TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.commit()


def _coerce_event(event: EventEnvelope | PersistedEvent) -> PersistedEvent:
    if isinstance(event, PersistedEvent):
        return event
    return PersistedEvent(
        event_id=event.event_id,
        event_type=event.event_type,
        timestamp=event.timestamp,
        task_id=event.task_id,
        run_id=event.run_id,
        correlation_id=event.correlation_id,
        source=event.source.to_dict(),
        payload=event.payload,
    )
