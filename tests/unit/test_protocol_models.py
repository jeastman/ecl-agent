from __future__ import annotations

import unittest

from packages.protocol.local_agent_protocol.models import (
    METHOD_TASK_APPROVE,
    METHOD_TASK_APPROVALS_LIST,
    METHOD_CONFIG_GET,
    METHOD_TASK_DIAGNOSTICS_LIST,
    DiagnosticEntry,
    EventEnvelope,
    EventSource,
    EventSourceKind,
    METHOD_MEMORY_INSPECT,
    METHOD_TASK_LOGS_STREAM,
    ApprovalDecisionPayload,
    ConfigGetResult,
    ConfigRedaction,
    MemoryInspectEntry,
    MemoryInspectParams,
    MemoryInspectResult,
    PROTOCOL_VERSION,
    RuntimeHealthResult,
    RuntimeEvent,
    TaskArtifactsListParams,
    TaskApproveParams,
    TaskApprovalsListParams,
    TaskDiagnosticsListParams,
    TaskDiagnosticsListResult,
    TaskCreateParams,
    TaskCreateRequest,
    TaskGetParams,
    TaskLogsStreamParams,
    TaskResumeParams,
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
            awaiting_approval=False,
            is_resumable=False,
            links={"events": METHOD_TASK_LOGS_STREAM},
        )
        payload = snapshot.to_dict()
        self.assertEqual(payload["status"], "executing")
        self.assertNotIn("failure", payload)
        self.assertEqual(payload["links"]["events"], METHOD_TASK_LOGS_STREAM)
        self.assertFalse(payload["awaiting_approval"])
        self.assertFalse(payload["is_resumable"])

    def test_task_query_params_validate(self) -> None:
        self.assertEqual(TaskGetParams.from_dict({"task_id": "task_1"}).task_id, "task_1")
        self.assertEqual(TaskResumeParams.from_dict({"task_id": "task_1"}).task_id, "task_1")
        self.assertEqual(
            TaskArtifactsListParams.from_dict({"task_id": "task_1"}).task_id,
            "task_1",
        )
        self.assertEqual(
            TaskApproveParams.from_dict(
                {
                    "task_id": "task_1",
                    "approval": {"approval_id": "approval_1", "decision": "approved"},
                }
            ).approval.approval_id,
            "approval_1",
        )
        self.assertTrue(
            TaskLogsStreamParams.from_dict(
                {"task_id": "task_1", "include_history": True}
            ).include_history
        )
        with self.assertRaisesRegex(ValueError, "task.resume requires task_id"):
            TaskResumeParams.from_dict({})
        with self.assertRaisesRegex(ValueError, "task.approve requires approval"):
            TaskApproveParams.from_dict({"task_id": "task_1"})
        self.assertIsNone(
            TaskApproveParams.from_dict(
                {"approval": {"approval_id": "approval_1", "decision": "approved"}}
            ).task_id
        )

    def test_memory_inspect_params_validate(self) -> None:
        params = MemoryInspectParams.from_dict(
            {
                "task_id": "task_1",
                "run_id": "run_1",
                "scope": "run_state",
                "namespace": "run.notes",
            }
        )
        self.assertEqual(params.task_id, "task_1")
        self.assertEqual(params.run_id, "run_1")
        self.assertEqual(params.scope, "run_state")
        self.assertEqual(params.namespace, "run.notes")
        self.assertEqual(METHOD_MEMORY_INSPECT, "memory.inspect")
        with self.assertRaisesRegex(ValueError, "memory.inspect run_id requires task_id"):
            MemoryInspectParams.from_dict({"run_id": "run_1"})
        self.assertEqual(METHOD_TASK_APPROVE, "task.approve")
        self.assertEqual(METHOD_TASK_APPROVALS_LIST, "task.approvals.list")

    def test_approval_payload_validation(self) -> None:
        payload = ApprovalDecisionPayload.from_dict(
            {"approval_id": "approval_1", "decision": "rejected"}
        )
        self.assertEqual(payload.decision, "rejected")
        with self.assertRaisesRegex(
            ValueError, "task.approve approval.decision must be approved or rejected"
        ):
            ApprovalDecisionPayload.from_dict({"approval_id": "approval_1", "decision": "approve"})

    def test_memory_inspect_result_serialization(self) -> None:
        result = MemoryInspectResult(
            entries=[
                MemoryInspectEntry(
                    memory_id="mem_1",
                    scope="project",
                    namespace="project.conventions",
                    content="Prefer explicit dataclasses.",
                    summary="Coding conventions",
                    provenance={"task_id": "task_1"},
                    created_at=utc_now_timestamp(),
                    updated_at=utc_now_timestamp(),
                )
            ],
            scope="project",
            count=1,
        )
        payload = result.to_dict()
        self.assertEqual(payload["scope"], "project")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["entries"][0]["memory_id"], "mem_1")

    def test_task_approvals_list_params_validate(self) -> None:
        params = TaskApprovalsListParams.from_dict({"task_id": "task_1", "run_id": "run_1"})
        self.assertEqual(params.task_id, "task_1")
        self.assertEqual(params.run_id, "run_1")
        with self.assertRaisesRegex(ValueError, "task.approvals.list requires task_id"):
            TaskApprovalsListParams.from_dict({})
        self.assertEqual(METHOD_TASK_DIAGNOSTICS_LIST, "task.diagnostics.list")

    def test_task_diagnostics_list_params_and_result_validate(self) -> None:
        params = TaskDiagnosticsListParams.from_dict({"task_id": "task_1", "run_id": "run_1"})
        self.assertEqual(params.task_id, "task_1")
        self.assertEqual(params.run_id, "run_1")
        with self.assertRaisesRegex(ValueError, "task.diagnostics.list requires task_id"):
            TaskDiagnosticsListParams.from_dict({})
        result = TaskDiagnosticsListResult(
            diagnostics=[
                DiagnosticEntry(
                    diagnostic_id="diag_1",
                    task_id="task_1",
                    run_id="run_1",
                    kind="policy_denied",
                    message="Denied",
                    created_at=utc_now_timestamp(),
                    details={"path": "workspace"},
                )
            ],
            count=1,
        )
        self.assertEqual(result.to_dict()["diagnostics"][0]["diagnostic_id"], "diag_1")

    def test_config_get_result_serialization(self) -> None:
        result = ConfigGetResult(
            effective_config={"runtime": {"name": "demo"}},
            loaded_profiles=[],
            config_sources=["docs/architecture/runtime.example.toml"],
            redactions=[ConfigRedaction(path="policy.api_token", reason="sensitive-key")],
        )
        payload = result.to_dict()
        self.assertEqual(payload["effective_config"]["runtime"]["name"], "demo")
        self.assertEqual(payload["redactions"][0]["path"], "policy.api_token")
        self.assertEqual(METHOD_CONFIG_GET, "config.get")

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
        self.assertEqual(EventType.SUBAGENT_COMPLETED.value, "subagent.completed")

    def test_runtime_health_result_serialization_omits_missing_capabilities(self) -> None:
        result = RuntimeHealthResult(
            protocol_version=PROTOCOL_VERSION,
            runtime_name="demo",
            runtime_version="0.1.0",
            status="ok",
            transport="stdio-jsonrpc",
            correlation_id="corr_1",
            identity={"path": "IDENTITY.md"},
            capabilities={"task_create": True, "event_stream": True},
        )
        payload = result.to_dict()
        self.assertTrue(payload["capabilities"]["task_create"])


if __name__ == "__main__":
    unittest.main()
