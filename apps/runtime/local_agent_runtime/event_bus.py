from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from queue import Queue
from threading import RLock
from typing import Protocol

from packages.observability.local_agent_observability.logging import emit_event
from packages.protocol.local_agent_protocol.models import RuntimeEvent


class EventBus(Protocol):
    def publish(self, event: RuntimeEvent) -> None: ...

    def list_events(
        self,
        task_id: str,
        run_id: str | None = None,
        from_event_id: str | None = None,
    ) -> list[RuntimeEvent]: ...

    @contextmanager
    def subscribe(self, task_id: str, run_id: str) -> Iterator[Queue[RuntimeEvent]]: ...


class InMemoryEventBus:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], list[RuntimeEvent]] = {}
        self._subscribers: dict[tuple[str, str], list[Queue[RuntimeEvent]]] = {}
        self._lock = RLock()

    def publish(self, event: RuntimeEvent) -> None:
        task_id = event.event.task_id
        run_id = event.event.run_id
        if task_id is None or run_id is None:
            raise ValueError("runtime task events must include task_id and run_id")
        key = (task_id, run_id)
        with self._lock:
            self._events.setdefault(key, []).append(event)
            subscribers = list(self._subscribers.get(key, []))
        for subscriber in subscribers:
            subscriber.put(event)
        emit_event(event)

    def list_events(
        self,
        task_id: str,
        run_id: str | None = None,
        from_event_id: str | None = None,
    ) -> list[RuntimeEvent]:
        with self._lock:
            if run_id is None:
                matching = [
                    event
                    for (candidate_task_id, _), events in self._events.items()
                    if candidate_task_id == task_id
                    for event in events
                ]
            else:
                matching = list(self._events.get((task_id, run_id), []))
        if from_event_id is None:
            return matching
        for index, event in enumerate(matching):
            if event.event.event_id == from_event_id:
                return matching[index + 1 :]
        return []

    @contextmanager
    def subscribe(self, task_id: str, run_id: str) -> Iterator[Queue[RuntimeEvent]]:
        queue: Queue[RuntimeEvent] = Queue()
        key = (task_id, run_id)
        with self._lock:
            self._subscribers.setdefault(key, []).append(queue)
        try:
            yield queue
        finally:
            with self._lock:
                subscribers = self._subscribers.get(key)
                if subscribers is None:
                    return
                self._subscribers[key] = [
                    candidate for candidate in subscribers if candidate is not queue
                ]
                if not self._subscribers[key]:
                    self._subscribers.pop(key, None)
