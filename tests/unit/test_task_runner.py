from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.runtime.local_agent_runtime.durable_services import create_durable_runtime_services
from apps.runtime.local_agent_runtime.event_bus import InMemoryEventBus
from apps.runtime.local_agent_runtime.run_state_store import InMemoryRunStateStore
from apps.runtime.local_agent_runtime.task_runner import (
    AgentExecutionResult,
    StubAgentHarness,
    TaskRunner,
)
from packages.config.local_agent_config.loader import load_runtime_config
from services.artifact_service.local_agent_artifact_service.store import InMemoryArtifactStore
from services.deepagent_runtime.local_agent_deepagent_runtime.tool_bindings import (
    SandboxToolBindings,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.interrupt_bridge import (
    InterruptBridge,
)
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

    def test_task_runner_translates_harness_callbacks_into_runtime_events(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=EventingHarness(),
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=[str(self.workspace_root)],
            identity_bundle_text="identity",
        )
        event_types = [event.event.event_type for event in bus.list_events(task_id, run_id)]
        self.assertEqual(
            event_types,
            [
                "task.created",
                "task.started",
                "plan.updated",
                "subagent.started",
                "tool.called",
                "artifact.created",
                "task.completed",
            ],
        )
        artifact = runner.list_artifacts(task_id, run_id)[0]
        self.assertEqual(artifact.logical_path, "artifacts/repo_summary.md")
        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.COMPLETED)
        self.assertEqual(snapshot.latest_summary, "Generated the repository summary artifact.")
        self.assertEqual(snapshot.active_subagent, "primary")

    def test_task_runner_marks_run_failed_when_harness_raises(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=RaisingHarness(),
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=[str(self.workspace_root)],
            identity_bundle_text="identity",
        )
        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.FAILED)
        failure = snapshot.failure
        self.assertIsNotNone(failure)
        assert failure is not None
        self.assertEqual(failure.message, "boom")
        self.assertEqual(bus.list_events(task_id, run_id)[-1].event.event_type, "task.failed")

    def test_task_runner_pauses_and_resumes_from_checkpoint_metadata(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        durable_services = create_durable_runtime_services(
            load_runtime_config("docs/architecture/runtime.example.toml"),
            runtime_root_override=str(self.runtime_root),
        )
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=PauseThenResumeHarness(),
            durable_services=durable_services,
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=[str(self.workspace_root)],
            identity_bundle_text="identity",
        )

        paused_snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(paused_snapshot.status, TaskStatus.PAUSED)
        self.assertTrue(paused_snapshot.is_resumable)
        self.assertEqual(paused_snapshot.pause_reason, "awaiting resume")
        self.assertIsNotNone(paused_snapshot.latest_checkpoint_id)
        self.assertIsNotNone(paused_snapshot.checkpoint_thread_id)

        resumed_snapshot = runner.resume_run(
            task_id,
            run_id,
            identity_bundle_text="identity",
        )
        self.assertEqual(resumed_snapshot.status, TaskStatus.COMPLETED)
        self.assertFalse(resumed_snapshot.is_resumable)
        self.assertIsNotNone(resumed_snapshot.latest_checkpoint_id)
        self.assertEqual(
            [event.event.event_type for event in bus.list_events(task_id, run_id)],
            [
                "task.created",
                "task.started",
                "checkpoint.saved",
                "task.paused",
                "task.resumed",
                "checkpoint.saved",
                "artifact.created",
                "task.completed",
            ],
        )
        metrics = durable_services.run_metrics_store.read_metrics(task_id, run_id)
        self.assertIsNotNone(metrics)
        assert metrics is not None
        self.assertEqual(metrics.checkpoint_count, 2)
        self.assertEqual(metrics.resume_count, 1)
        self.assertEqual(metrics.event_count, 8)
        self.assertEqual(metrics.artifact_count, 1)
        self.assertIsNotNone(metrics.started_at)
        self.assertIsNotNone(metrics.ended_at)

    def test_task_runner_requests_approval_and_resumes_after_approval(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        durable_services = create_durable_runtime_services(
            load_runtime_config("docs/architecture/runtime.example.toml"),
            runtime_root_override=str(self.runtime_root),
        )
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=ApprovalThenResumeHarness(),
            durable_services=durable_services,
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Edit governed files",
            workspace_roots=[str(self.workspace_root)],
            identity_bundle_text="identity",
        )

        awaiting = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(awaiting.status, TaskStatus.AWAITING_APPROVAL)
        self.assertTrue(awaiting.awaiting_approval)
        assert awaiting.pending_approval_id is not None

        approval_id, accepted, status, snapshot = runner.approve(
            task_id,
            awaiting.pending_approval_id,
            "approved",
            run_id=run_id,
            identity_bundle_text="identity",
        )

        self.assertEqual(approval_id, awaiting.pending_approval_id)
        self.assertTrue(accepted)
        self.assertEqual(status, "approved")
        self.assertEqual(snapshot.status, TaskStatus.COMPLETED)
        event_types = [event.event.event_type for event in bus.list_events(task_id, run_id)]
        self.assertEqual(event_types.count("approval.requested"), 1)
        self.assertIn("task.resumed", event_types)
        metrics = durable_services.run_metrics_store.read_metrics(task_id, run_id)
        assert metrics is not None
        self.assertEqual(metrics.approval_count, 1)
        self.assertEqual(metrics.resume_count, 1)

    def test_task_runner_fails_run_when_approval_rejected(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        durable_services = create_durable_runtime_services(
            load_runtime_config("docs/architecture/runtime.example.toml"),
            runtime_root_override=str(self.runtime_root),
        )
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=ApprovalThenResumeHarness(),
            durable_services=durable_services,
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Edit governed files",
            workspace_roots=[str(self.workspace_root)],
            identity_bundle_text="identity",
        )
        awaiting = runner.get_task_snapshot(task_id, run_id)
        assert awaiting.pending_approval_id is not None

        _, accepted, status, snapshot = runner.approve(
            task_id,
            awaiting.pending_approval_id,
            "rejected",
            run_id=run_id,
            identity_bundle_text="identity",
        )

        self.assertFalse(accepted)
        self.assertEqual(status, "rejected")
        self.assertEqual(snapshot.status, TaskStatus.FAILED)
        self.assertFalse(snapshot.awaiting_approval)
        self.assertIsNone(snapshot.pending_approval_id)

    def test_task_runner_denies_network_command(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        durable_services = create_durable_runtime_services(
            load_runtime_config("docs/architecture/runtime.example.toml"),
            runtime_root_override=str(self.runtime_root),
        )
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=NetworkDeniedHarness(),
            durable_services=durable_services,
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Attempt network access",
            workspace_roots=[str(self.workspace_root)],
            identity_bundle_text="identity",
        )

        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.FAILED)
        metrics = durable_services.run_metrics_store.read_metrics(task_id, run_id)
        assert metrics is not None
        self.assertEqual(metrics.deny_count, 1)
        self.assertFalse(snapshot.is_resumable)
        assert snapshot.latest_summary is not None
        self.assertIn("network access", snapshot.latest_summary.lower())
        self.assertIn(
            "policy.denied",
            [event.event.event_type for event in bus.list_events(task_id, run_id)],
        )


class EventingHarness:
    def execute(self, request, on_event=None) -> AgentExecutionResult:
        if on_event is not None:
            on_event(
                "plan.updated",
                {"phase": "planning", "summary": "Building the execution plan."},
            )
            on_event(
                "subagent.started",
                {
                    "role": "primary",
                    "name": "repo-summarizer",
                    "summary": "Primary agent execution started.",
                },
            )
            on_event(
                "tool.called",
                {"tool": "write_file", "path": "workspace/artifacts/repo_summary.md"},
            )
        request.sandbox.write_text("workspace/artifacts/repo_summary.md", "# Summary\n")
        return AgentExecutionResult(
            success=True,
            summary="Generated the repository summary artifact.",
            output_artifacts=["workspace/artifacts/repo_summary.md"],
        )


class RaisingHarness:
    def execute(self, request, on_event=None) -> AgentExecutionResult:
        raise RuntimeError("boom")


class PauseThenResumeHarness:
    def execute(self, request, on_event=None) -> AgentExecutionResult:
        controller = request.checkpoint_controller
        if controller is None:
            raise AssertionError("checkpoint controller is required for pause/resume tests")
        if request.resume_from_checkpoint_id is None:
            metadata = controller.record_checkpoint("pause_requested")
            if on_event is not None:
                on_event("checkpoint.saved", metadata.to_dict())
            return AgentExecutionResult(
                success=False,
                summary="Paused until explicitly resumed.",
                output_artifacts=[],
                paused=True,
                pause_reason="awaiting resume",
            )
        metadata = controller.record_checkpoint("resumed")
        if on_event is not None:
            on_event("checkpoint.saved", metadata.to_dict())
        request.sandbox.write_text("workspace/artifacts/resumed.md", "# Resumed\n")
        return AgentExecutionResult(
            success=True,
            summary="Completed after resume.",
            output_artifacts=["workspace/artifacts/resumed.md"],
        )


class ApprovalThenResumeHarness:
    def execute(self, request, on_event=None) -> AgentExecutionResult:
        bridge = InterruptBridge(
            governed_operation=request.governed_operation,
            checkpoint_controller=request.checkpoint_controller,
            on_event=on_event,
        )
        bindings = SandboxToolBindings(
            sandbox=request.sandbox,
            task_id=request.task_id,
            run_id=request.run_id,
            on_event=on_event,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=bridge.authorize,
        )
        bindings.write_file("workspace/apps/runtime/guarded.txt", "content\n")
        return AgentExecutionResult(
            success=True,
            summary="Governed write completed after approval.",
            output_artifacts=[],
        )


class NetworkDeniedHarness:
    def execute(self, request, on_event=None) -> AgentExecutionResult:
        bridge = InterruptBridge(
            governed_operation=request.governed_operation,
            checkpoint_controller=request.checkpoint_controller,
            on_event=on_event,
        )
        bindings = SandboxToolBindings(
            sandbox=request.sandbox,
            task_id=request.task_id,
            run_id=request.run_id,
            on_event=on_event,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=bridge.authorize,
        )
        bindings.execute_command(["curl", "https://example.com"], cwd="workspace")
        return AgentExecutionResult(success=True, summary="unexpected", output_artifacts=[])


if __name__ == "__main__":
    unittest.main()
