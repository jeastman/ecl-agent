from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.runtime.local_agent_runtime.event_bus import InMemoryEventBus
from apps.runtime.local_agent_runtime.run_state_store import InMemoryRunStateStore
from apps.runtime.local_agent_runtime.task_runner import StubAgentHarness, TaskRunner
from services.artifact_service.local_agent_artifact_service.store import InMemoryArtifactStore
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    LocalExecutionSandboxFactory,
)
from packages.task_model.local_agent_task_model.models import TaskStatus


class TaskRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self._temp_dir.cleanup)
        self.workspace_root = Path(self._temp_dir.name) / "workspace"
        self.workspace_root.mkdir()
        self.runtime_root = Path(self._temp_dir.name) / "runtime"
        self.sandbox_factory = LocalExecutionSandboxFactory(runtime_root=self.runtime_root)

    def test_task_runner_emits_expected_event_order_on_success(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=StubAgentHarness(),
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=[str(self.workspace_root)],
            identity_bundle_text="identity",
        )
        event_types = [event.event.event_type for event in bus.list_events(task_id, run_id)]
        self.assertEqual(event_types, ["task.created", "task.started", "task.completed"])
        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.COMPLETED)

    def test_task_runner_registers_artifacts_and_updates_count(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=StubAgentHarness(output_artifact_path="scratch/repo_summary.md"),
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=[str(self.workspace_root)],
            identity_bundle_text="identity",
        )
        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.artifact_count, 1)
        artifacts = runner.list_artifacts(task_id, run_id)
        self.assertEqual(artifacts[0].logical_path, "scratch/repo_summary.md")
        event_types = [event.event.event_type for event in bus.list_events(task_id, run_id)]
        self.assertEqual(
            event_types,
            ["task.created", "task.started", "artifact.created", "task.completed"],
        )
        artifact_event = bus.list_events(task_id, run_id)[2]
        self.assertEqual(
            artifact_event.event.payload["artifact"]["logical_path"],
            "scratch/repo_summary.md",
        )

    def test_task_runner_records_failure(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=StubAgentHarness(success=False),
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=[str(self.workspace_root)],
            identity_bundle_text="identity",
        )
        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.FAILED)
        self.assertEqual(bus.list_events(task_id, run_id)[-1].event.event_type, "task.failed")


if __name__ == "__main__":
    unittest.main()
