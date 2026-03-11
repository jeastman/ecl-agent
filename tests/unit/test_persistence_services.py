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


class RuntimeStateTests(unittest.TestCase):
    def test_task_snapshot_exposes_phase_one_resumability_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            runtime_root = Path(temp_dir) / "runtime"
            workspace_root.mkdir()
            sandbox_factory = LocalExecutionSandboxFactory(runtime_root=runtime_root)
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
            "services.policy_service.local_agent_policy_service.policy_engine",
            "services.policy_service.local_agent_policy_service.approval_store",
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


class RunMetricsStoreTests(unittest.TestCase):
    def test_run_metrics_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            store = SQLiteRunMetricsStore(str(Path(temp_dir) / "runtime.db"))
            record = RunMetricsRecord(
                task_id="task_1",
                run_id="run_1",
                checkpoint_count=2,
                approval_count=1,
                resume_count=1,
                last_updated_at=utc_now_timestamp(),
            )

            store.write_metrics(record)

            loaded = store.read_metrics("task_1", "run_1")

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.checkpoint_count, 2)


if __name__ == "__main__":
    unittest.main()
