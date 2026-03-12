from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from apps.runtime.local_agent_runtime.event_bus import InMemoryEventBus
from apps.runtime.local_agent_runtime.run_state_store import InMemoryRunStateStore
from apps.runtime.local_agent_runtime.task_runner import StubAgentHarness, TaskRunner
from packages.protocol.local_agent_protocol.models import utc_now_timestamp
from packages.task_model.local_agent_task_model.models import TaskStatus
from services.artifact_service.local_agent_artifact_service.store import InMemoryArtifactStore
from services.checkpoint_service.local_agent_checkpoint_service.checkpoint_models import (
    CheckpointMetadata,
)
from services.checkpoint_service.local_agent_checkpoint_service.checkpoint_store import (
    SQLiteCheckpointStore,
)
from services.checkpoint_service.local_agent_checkpoint_service.thread_registry import (
    SQLiteThreadRegistry,
)
from services.memory_service.local_agent_memory_service.memory_models import MemoryRecord
from services.memory_service.local_agent_memory_service.memory_promotion import (
    MEMORY_SCOPE_IDENTITY,
    MEMORY_SCOPE_PROJECT,
    MEMORY_SCOPE_RUN_STATE,
    MEMORY_SCOPE_SCRATCH,
    MemoryPromotionService,
)
from services.memory_service.local_agent_memory_service.memory_store import SQLiteMemoryStore
from services.observability_service.local_agent_observability_service.event_store import (
    SQLiteEventStore,
)
from services.observability_service.local_agent_observability_service.observability_models import (
    DiagnosticRecord,
    PersistedEvent,
    RunMetricsRecord,
)
from services.observability_service.local_agent_observability_service.run_metrics_store import (
    SQLiteRunMetricsStore,
)
from services.policy_service.local_agent_policy_service.approval_store import (
    SQLiteApprovalStore,
)
from services.policy_service.local_agent_policy_service.boundary_scope import (
    BoundaryGrant,
    SQLiteBoundaryGrantStore,
)
from services.policy_service.local_agent_policy_service.policy_engine import RuntimePolicyEngine
from services.policy_service.local_agent_policy_service.policy_models import (
    ApprovalRequest,
    OperationContext,
)
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    LocalExecutionSandboxFactory,
)


class PersistenceModelTests(unittest.TestCase):
    def test_new_dataclasses_round_trip_to_dict(self) -> None:
        event = PersistedEvent(
            event_id="evt_1",
            event_type="task.created",
            timestamp=utc_now_timestamp(),
            task_id="task_1",
            run_id="run_1",
            correlation_id="corr_1",
            source={"kind": "runtime"},
            payload={"status": "created"},
        )
        diagnostic = DiagnosticRecord(
            diagnostic_id="diag_1",
            task_id="task_1",
            run_id="run_1",
            kind="runtime",
            message="boom",
            created_at=utc_now_timestamp(),
            details={"phase": "execute"},
        )
        metrics = RunMetricsRecord(task_id="task_1", run_id="run_1", checkpoint_count=1)

        self.assertEqual(event.to_dict()["event_id"], "evt_1")
        self.assertEqual(diagnostic.to_dict()["kind"], "runtime")
        self.assertEqual(metrics.to_dict()["checkpoint_count"], 1)


class ThreadRegistryTests(unittest.TestCase):
    def test_thread_registry_and_resume_handle_lookup(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            database_path = str(Path(temp_dir) / "runtime.db")
            registry = SQLiteThreadRegistry(database_path)
            store = SQLiteCheckpointStore(database_path, thread_registry=registry)

            self.assertIsNone(registry.get_thread_id("task_1", "run_1"))

            registry.bind_thread("task_1", "run_1", "thread_a")
            registry.bind_thread("task_1", "run_1", "thread_b")
            store.save_metadata(
                CheckpointMetadata(
                    checkpoint_id="ckpt_1",
                    task_id="task_1",
                    run_id="run_1",
                    thread_id="thread_b",
                    checkpoint_index=0,
                    created_at=utc_now_timestamp(),
                )
            )

            handle = store.get_resume_handle("task_1", "run_1")

            self.assertEqual(registry.get_thread_id("task_1", "run_1"), "thread_b")
            self.assertIsNotNone(handle)
            assert handle is not None
            self.assertEqual(handle.thread_id, "thread_b")
            self.assertEqual(handle.latest_checkpoint_id, "ckpt_1")

    def test_checkpoint_store_create_thread_and_empty_resume_handle(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            database_path = str(Path(temp_dir) / "runtime.db")
            registry = SQLiteThreadRegistry(database_path)
            store = SQLiteCheckpointStore(database_path, thread_registry=registry)

            thread_id = store.create_thread("task_1", "run_1")
            handle = store.get_resume_handle("task_1", "run_1")

            self.assertTrue(thread_id.startswith("thread_"))
            self.assertIsNotNone(handle)
            assert handle is not None
            self.assertEqual(handle.thread_id, thread_id)
            self.assertIsNone(handle.latest_checkpoint_id)


class MemoryStoreTests(unittest.TestCase):
    def test_memory_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            store = SQLiteMemoryStore(str(Path(temp_dir) / "runtime.db"))
            record = MemoryRecord(
                memory_id="mem_1",
                scope="project",
                namespace="project.conventions",
                content="Prefer explicit dataclasses.",
                summary="Coding conventions",
                provenance={"task_id": "task_1"},
                created_at=utc_now_timestamp(),
                updated_at=utc_now_timestamp(),
            )

            store.write_memory(record)

            loaded = store.read_memory("mem_1")
            listed = store.list_memory(scope="project", namespace="project.conventions")

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.summary, record.summary)
            self.assertEqual(len(listed), 1)

    def test_memory_store_orders_and_filters_entries(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            store = SQLiteMemoryStore(str(Path(temp_dir) / "runtime.db"))
            store.write_memory(
                MemoryRecord(
                    memory_id="mem_b",
                    scope=MEMORY_SCOPE_PROJECT,
                    namespace="project.conventions",
                    content="Second",
                    summary="Second",
                    provenance={"task_id": "task_1"},
                    created_at="2026-03-10T00:00:01Z",
                    updated_at="2026-03-10T00:00:01Z",
                )
            )
            store.write_memory(
                MemoryRecord(
                    memory_id="mem_a",
                    scope=MEMORY_SCOPE_PROJECT,
                    namespace="project.conventions",
                    content="First",
                    summary="First",
                    provenance={"task_id": "task_1"},
                    created_at="2026-03-10T00:00:01Z",
                    updated_at="2026-03-10T00:00:01Z",
                )
            )
            store.write_memory(
                MemoryRecord(
                    memory_id="scratch_1",
                    scope=MEMORY_SCOPE_SCRATCH,
                    namespace="scratch.notes",
                    content="Scratch",
                    summary="Scratch",
                    provenance={"task_id": "task_1"},
                    created_at="2026-03-10T00:00:02Z",
                    updated_at="2026-03-10T00:00:02Z",
                )
            )

            listed = store.list_memory(scope=MEMORY_SCOPE_PROJECT, namespace="project.conventions")

            self.assertEqual([record.memory_id for record in listed], ["mem_a", "mem_b"])

    def test_memory_store_deletes_records(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            store = SQLiteMemoryStore(str(Path(temp_dir) / "runtime.db"))
            store.write_memory(
                MemoryRecord(
                    memory_id="mem_1",
                    scope=MEMORY_SCOPE_PROJECT,
                    namespace="project.conventions",
                    content="Delete me",
                    summary="Delete me",
                    provenance={"task_id": "task_1"},
                    created_at="2026-03-10T00:00:00Z",
                    updated_at="2026-03-10T00:00:00Z",
                )
            )

            store.delete_memory("mem_1")

            self.assertIsNone(store.read_memory("mem_1"))
            self.assertEqual(store.list_memory(scope=MEMORY_SCOPE_PROJECT), [])

    def test_memory_store_promotes_run_state_record_to_project(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            store = SQLiteMemoryStore(str(Path(temp_dir) / "runtime.db"))
            store.write_memory(
                MemoryRecord(
                    memory_id="mem_1",
                    scope=MEMORY_SCOPE_RUN_STATE,
                    namespace="run.notes",
                    content="Observed repository convention",
                    summary="Convention",
                    provenance={"task_id": "task_1", "run_id": "run_1"},
                    created_at="2026-03-10T00:00:00Z",
                    updated_at="2026-03-10T00:00:00Z",
                    source_run="run_1",
                    confidence=0.9,
                )
            )

            promoted = store.promote_memory("mem_1")

            self.assertIsNotNone(promoted)
            assert promoted is not None
            self.assertEqual(promoted.scope, MEMORY_SCOPE_PROJECT)
            self.assertEqual(promoted.source_run, "run_1")
            self.assertEqual(promoted.confidence, 0.9)
            self.assertEqual(promoted.provenance["promotion"]["from_scope"], MEMORY_SCOPE_RUN_STATE)
            self.assertEqual(store.read_memory("mem_1").scope, MEMORY_SCOPE_PROJECT)  # type: ignore[union-attr]

    def test_memory_store_promotes_scratch_record_to_project(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            store = SQLiteMemoryStore(str(Path(temp_dir) / "runtime.db"))
            store.write_memory(
                MemoryRecord(
                    memory_id="mem_1",
                    scope=MEMORY_SCOPE_SCRATCH,
                    namespace="scratch.notes",
                    content="Useful scratch fact",
                    summary="Scratch fact",
                    provenance={"task_id": "task_1"},
                    created_at="2026-03-10T00:00:00Z",
                    updated_at="2026-03-10T00:00:00Z",
                )
            )

            promoted = store.promote_memory("mem_1")

            self.assertIsNotNone(promoted)
            assert promoted is not None
            self.assertEqual(promoted.scope, MEMORY_SCOPE_PROJECT)

    def test_memory_store_rejects_invalid_promotions(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            store = SQLiteMemoryStore(str(Path(temp_dir) / "runtime.db"))
            store.write_memory(
                MemoryRecord(
                    memory_id="identity_1",
                    scope=MEMORY_SCOPE_IDENTITY,
                    namespace="identity.bundle",
                    content="Identity",
                    summary="Identity",
                    provenance={"source_path": "IDENTITY.md"},
                    created_at="2026-03-10T00:00:00Z",
                    updated_at="2026-03-10T00:00:00Z",
                )
            )

            self.assertIsNone(store.promote_memory("missing"))
            with self.assertRaisesRegex(ValueError, "not promotable"):
                store.promote_memory("identity_1")
            with self.assertRaisesRegex(ValueError, "target must be project"):
                store.promote_memory("identity_1", target_scope=MEMORY_SCOPE_RUN_STATE)

    def test_memory_promotion_service_limits_agent_writable_scopes(self) -> None:
        service = MemoryPromotionService()

        self.assertTrue(service.can_agent_write(MEMORY_SCOPE_RUN_STATE))
        self.assertTrue(service.can_agent_write(MEMORY_SCOPE_SCRATCH))
        self.assertFalse(service.can_agent_write(MEMORY_SCOPE_PROJECT))
        self.assertFalse(service.can_agent_write(MEMORY_SCOPE_IDENTITY))


class RuntimeStateTests(unittest.TestCase):
    def test_task_snapshot_exposes_phase_one_resumability_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            runtime_root = Path(temp_dir) / "runtime"
            workspace_root.mkdir()
            sandbox_factory = LocalExecutionSandboxFactory(
                runtime_root=runtime_root,
                governed_workspace_root=workspace_root,
            )
            runner = TaskRunner(
                run_state_store=InMemoryRunStateStore(),
                event_bus=InMemoryEventBus(),
                artifact_store=InMemoryArtifactStore(path_mapper=sandbox_factory),
                sandbox_factory=sandbox_factory,
                agent_harness=StubAgentHarness(),
            )
            task_id, run_id, _ = runner.start_run(
                correlation_id="corr_1",
                objective="Inspect the repo",
                workspace_roots=[str(workspace_root)],
                identity_bundle_text="identity",
            )

            snapshot = runner.get_task_snapshot(task_id, run_id)

            self.assertEqual(snapshot.status, TaskStatus.COMPLETED)
            self.assertFalse(snapshot.awaiting_approval)
            self.assertFalse(snapshot.is_resumable)
            self.assertIsNone(snapshot.pause_reason)
            self.assertIsNone(snapshot.pending_approval_id)


class InterfaceIsolationTests(unittest.TestCase):
    def test_runtime_facing_interfaces_do_not_reference_langgraph_or_langchain(self) -> None:
        modules = [
            "services.checkpoint_service.local_agent_checkpoint_service.checkpoint_store",
            "services.checkpoint_service.local_agent_checkpoint_service.thread_registry",
            "services.memory_service.local_agent_memory_service.memory_store",
            "services.memory_service.local_agent_memory_service.memory_promotion",
            "services.policy_service.local_agent_policy_service.policy_engine",
            "services.policy_service.local_agent_policy_service.approval_store",
            "services.policy_service.local_agent_policy_service.boundary_scope",
            "services.observability_service.local_agent_observability_service.event_store",
            "services.observability_service.local_agent_observability_service.diagnostic_store",
            "services.observability_service.local_agent_observability_service.run_metrics_store",
        ]

        for module_name in modules:
            module = __import__(module_name, fromlist=["_sentinel"])
            source = inspect.getsource(module).lower()
            self.assertNotIn("langgraph", source)
            self.assertNotIn("langchain", source)


class EventStoreTests(unittest.TestCase):
    def test_event_store_appends_and_reads_events(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            store = SQLiteEventStore(str(Path(temp_dir) / "runtime.db"))
            event = PersistedEvent(
                event_id="evt_1",
                event_type="task.created",
                timestamp=utc_now_timestamp(),
                task_id="task_1",
                run_id="run_1",
                correlation_id="corr_1",
                source={"kind": "runtime"},
                payload={"status": "created"},
            )

            store.append_event(event)

            events = store.get_events("task_1", "run_1")

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].event_id, "evt_1")
            self.assertEqual(store.list_run_keys(), [("task_1", "run_1")])


class RunMetricsStoreTests(unittest.TestCase):
    def test_run_metrics_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            store = SQLiteRunMetricsStore(str(Path(temp_dir) / "runtime.db"))
            record = RunMetricsRecord(
                task_id="task_1",
                run_id="run_1",
                started_at="2026-03-10T00:00:00Z",
                ended_at="2026-03-10T00:10:00Z",
                event_count=4,
                artifact_count=1,
                checkpoint_count=2,
                approval_count=1,
                resume_count=1,
                deny_count=1,
                last_updated_at=utc_now_timestamp(),
            )

            store.write_metrics(record)

            loaded = store.read_metrics("task_1", "run_1")

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.started_at, "2026-03-10T00:00:00Z")
            self.assertEqual(loaded.event_count, 4)
            self.assertEqual(loaded.artifact_count, 1)
            self.assertEqual(loaded.checkpoint_count, 2)
            self.assertEqual(loaded.deny_count, 1)


class ApprovalAndPolicyTests(unittest.TestCase):
    def test_approval_store_round_trip_and_reject_duplicate_decision(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            store = SQLiteApprovalStore(str(Path(temp_dir) / "runtime.db"))
            request = ApprovalRequest(
                approval_id="approval_1",
                task_id="task_1",
                run_id="run_1",
                type="boundary",
                scope={"boundary_key": "file.write:/apps/runtime/**"},
                description="Allow writes to /apps/runtime/** for this run",
                created_at=utc_now_timestamp(),
                status="pending",
            )

            store.create_request(request)
            approved = store.decide("approval_1", "approved", utc_now_timestamp())

            self.assertEqual(approved.status, "approved")
            self.assertEqual(store.list_for_task("task_1")[0].decision, "approved")
            with self.assertRaisesRegex(ValueError, "already approved"):
                store.decide("approval_1", "rejected", utc_now_timestamp())

    def test_boundary_grant_store_reuses_granted_boundary(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            store = SQLiteBoundaryGrantStore(str(Path(temp_dir) / "runtime.db"))
            store.grant(
                BoundaryGrant(
                    task_id="task_1",
                    run_id="run_1",
                    boundary_key="file.write:/apps/runtime/**",
                    approval_id="approval_1",
                    granted_at=utc_now_timestamp(),
                )
            )

            self.assertTrue(store.has_grant("task_1", "run_1", "file.write:/apps/runtime/**"))
            self.assertFalse(store.has_grant("task_1", "run_2", "file.write:/apps/runtime/**"))

    def test_runtime_policy_engine_classifies_allow_require_and_deny(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            grants = SQLiteBoundaryGrantStore(str(Path(temp_dir) / "runtime.db"))
            engine = RuntimePolicyEngine(policy_config={}, boundary_grants=grants)

            allow = engine.evaluate(
                OperationContext(
                    task_id="task_1",
                    run_id="run_1",
                    operation_type="file.write",
                    path_scope="/artifacts/out.md",
                )
            )
            require = engine.evaluate(
                OperationContext(
                    task_id="task_1",
                    run_id="run_1",
                    operation_type="file.write",
                    path_scope="/apps/runtime/main.py",
                )
            )
            deny = engine.evaluate(
                OperationContext(
                    task_id="task_1",
                    run_id="run_1",
                    operation_type="command.execute",
                    command_class="network",
                    path_scope="/",
                )
            )

            self.assertEqual(allow.decision, "ALLOW")
            self.assertEqual(require.decision, "REQUIRE_APPROVAL")
            self.assertEqual(deny.decision, "DENY")

    def test_runtime_policy_engine_classifies_memory_operations(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            grants = SQLiteBoundaryGrantStore(str(Path(temp_dir) / "runtime.db"))
            engine = RuntimePolicyEngine(policy_config={}, boundary_grants=grants)

            allow = engine.evaluate(
                OperationContext(
                    task_id="task_1",
                    run_id="run_1",
                    operation_type="memory.write",
                    memory_scope=MEMORY_SCOPE_RUN_STATE,
                    namespace="run.notes",
                )
            )
            require = engine.evaluate(
                OperationContext(
                    task_id="task_1",
                    run_id="run_1",
                    operation_type="memory.write",
                    memory_scope=MEMORY_SCOPE_PROJECT,
                    namespace="project.conventions",
                )
            )
            deny = engine.evaluate(
                OperationContext(
                    task_id="task_1",
                    run_id="run_1",
                    operation_type="memory.write",
                    memory_scope=MEMORY_SCOPE_IDENTITY,
                    namespace="identity.bundle",
                )
            )

            self.assertEqual(allow.decision, "ALLOW")
            self.assertEqual(require.decision, "REQUIRE_APPROVAL")
            self.assertEqual(require.boundary_key, "memory.write:project:project.conventions")
            self.assertEqual(deny.decision, "DENY")


if __name__ == "__main__":
    unittest.main()
