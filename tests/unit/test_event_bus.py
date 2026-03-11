from __future__ import annotations

import unittest

from apps.runtime.local_agent_runtime.event_bus import InMemoryEventBus
from packages.protocol.local_agent_protocol.models import (
    EventEnvelope,
    EventSource,
    EventSourceKind,
    RuntimeEvent,
    utc_now_timestamp,
)
from packages.task_model.local_agent_task_model.models import EventType


class EventBusTests(unittest.TestCase):
    def test_list_events_preserves_order_and_replay(self) -> None:
        bus = InMemoryEventBus()
        first = RuntimeEvent(
            event=EventEnvelope(
                event_id="evt_1",
                event_type=EventType.TASK_CREATED.value,
                timestamp=utc_now_timestamp(),
                correlation_id="corr_1",
                task_id="task_1",
                run_id="run_1",
                source=EventSource(kind=EventSourceKind.RUNTIME, component="tests"),
                payload={"status": "created"},
            )
        )
        second = RuntimeEvent(
            event=EventEnvelope(
                event_id="evt_2",
                event_type=EventType.TASK_STARTED.value,
                timestamp=utc_now_timestamp(),
                correlation_id="corr_1",
                task_id="task_1",
                run_id="run_1",
                source=EventSource(kind=EventSourceKind.RUNTIME, component="tests"),
                payload={"status": "executing"},
            )
        )
        bus.publish(first)
        bus.publish(second)
        events = bus.list_events("task_1", "run_1")
        replay = bus.list_events("task_1", "run_1", from_event_id="evt_1")
        self.assertEqual([event.event.event_id for event in events], ["evt_1", "evt_2"])
        self.assertEqual([event.event.event_id for event in replay], ["evt_2"])


if __name__ == "__main__":
    unittest.main()
