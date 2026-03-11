from __future__ import annotations

import unittest

from packages.protocol.local_agent_protocol.models import (
    EventEnvelope,
    EventSource,
    EventSourceKind,
    METHOD_TASK_LOGS_STREAM,
    PROTOCOL_VERSION,
    RuntimeEvent,
    TaskArtifactsListParams,
    TaskCreateParams,
    TaskCreateRequest,
    TaskGetParams,
    TaskLogsStreamParams,
    TaskSnapshot,
    utc_now_timestamp,
)
from packages.task_model.local_agent_task_model.models import EventType, TaskStatus


class ProtocolModelTests(unittest.TestCase):
    def test_task_create_params_round_trip(self) -> None:
        params = TaskCreateParams(
            task=TaskCreateRequest(
                objective="Inspect the repo",
                workspace_roots=["."],
                constraints=["stay in repo"],
                success_criteria=["return a summary"],
            )
        )
        parsed = TaskCreateParams.from_dict(params.to_dict())
        self.assertEqual(parsed.task.objective, "Inspect the repo")
        self.assertEqual(parsed.task.workspace_roots, ["."])

    def test_task_create_requires_workspace_roots(self) -> None:
        with self.assertRaisesRegex(ValueError, "task.create requires task.workspace_roots"):
            TaskCreateParams.from_dict({"task": {"objective": "Inspect the repo"}})

    def test_task_snapshot_serialization_omits_none(self) -> None:
        snapshot = TaskSnapshot(
            task_id="task_1",
            run_id="run_1",
            status=TaskStatus.EXECUTING,
            objective="Inspect the repo",
            created_at=utc_now_timestamp(),
            updated_at=utc_now_timestamp(),
            links={"events": METHOD_TASK_LOGS_STREAM},
        )
        payload = snapshot.to_dict()
        self.assertEqual(payload["status"], "executing")
        self.assertNotIn("failure", payload)
        self.assertEqual(payload["links"]["events"], METHOD_TASK_LOGS_STREAM)

    def test_task_query_params_validate(self) -> None:
        self.assertEqual(TaskGetParams.from_dict({"task_id": "task_1"}).task_id, "task_1")
        self.assertEqual(
            TaskArtifactsListParams.from_dict({"task_id": "task_1"}).task_id,
            "task_1",
        )
        self.assertTrue(
            TaskLogsStreamParams.from_dict(
                {"task_id": "task_1", "include_history": True}
            ).include_history
        )

    def test_runtime_event_serialization(self) -> None:
        event = RuntimeEvent(
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
        payload = event.to_dict()
        self.assertEqual(payload["type"], "runtime.event")
        self.assertEqual(payload["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(payload["event"]["source"]["component"], "tests")


if __name__ == "__main__":
    unittest.main()
