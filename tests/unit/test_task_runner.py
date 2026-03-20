from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.runtime.local_agent_runtime.durable_services import create_durable_runtime_services
from apps.runtime.local_agent_runtime.event_bus import InMemoryEventBus
from apps.runtime.local_agent_runtime.run_state_store import InMemoryRunStateStore
from apps.runtime.local_agent_runtime.conversation_compaction_service import (
    ConversationCompactionService,
)
from apps.runtime.local_agent_runtime.task_runner import (
    AgentExecutionResult,
    StubAgentHarness,
    TaskRunner,
)
from packages.config.local_agent_config.loader import load_runtime_config
from packages.config.local_agent_config.models import CompactionConfig
from services.artifact_service.local_agent_artifact_service.store import InMemoryArtifactStore
from services.deepagent_runtime.local_agent_deepagent_runtime.compaction_strategy import (
    CompactionResult,
    CompactionSnapshot,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.tool_bindings import (
    SandboxToolBindings,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.interrupt_bridge import (
    InterruptBridge,
)
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    LocalExecutionSandboxFactory,
)
from packages.task_model.local_agent_task_model.models import EventType
from packages.task_model.local_agent_task_model.models import TaskStatus


class TaskRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self._temp_dir.cleanup)
        self.workspace_root = Path(self._temp_dir.name) / "workspace"
        self.workspace_root.mkdir()
        self.runtime_root = Path(self._temp_dir.name) / "runtime"
        self.sandbox_factory = LocalExecutionSandboxFactory(
            runtime_root=self.runtime_root,
            governed_workspace_root=self.workspace_root,
        )

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
            workspace_roots=["/workspace"],
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
            agent_harness=StubAgentHarness(output_artifact_path="/tmp/repo_summary.md"),
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )
        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.artifact_count, 1)
        artifacts = runner.list_artifacts(task_id, run_id)
        self.assertEqual(artifacts[0].logical_path, "/tmp/repo_summary.md")
        event_types = [event.event.event_type for event in bus.list_events(task_id, run_id)]
        self.assertEqual(
            event_types,
            ["task.created", "task.started", "artifact.created", "task.completed"],
        )
        artifact_event = bus.list_events(task_id, run_id)[2]
        self.assertEqual(
            artifact_event.event.payload["artifact"]["logical_path"],
            "/tmp/repo_summary.md",
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
            workspace_roots=["/workspace"],
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
            workspace_roots=["/workspace"],
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
                "subagent.completed",
                "tool.called",
                "tool.called",
                "artifact.created",
                "task.completed",
            ],
        )
        artifact = runner.list_artifacts(task_id, run_id)[0]
        self.assertEqual(artifact.logical_path, "/workspace/artifacts/repo_summary.md")
        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.COMPLETED)
        self.assertEqual(snapshot.latest_summary, "Generated the repository summary artifact.")
        self.assertIsNone(snapshot.active_subagent)
        assert snapshot.todos is not None
        self.assertEqual(
            [todo.content for todo in snapshot.todos],
            ["Inspect files", "Write summary"],
        )
        self.assertEqual(snapshot.todos[1].status.value, "in_progress")

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
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )
        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.FAILED)
        failure = snapshot.failure
        self.assertIsNotNone(failure)
        assert failure is not None
        self.assertEqual(failure.message, "boom")
        self.assertEqual(bus.list_events(task_id, run_id)[-1].event.event_type, "task.failed")

    def test_task_runner_registers_run_scoped_final_response_artifact_and_preview(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=FinalResponseHarness(),
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )

        artifacts = runner.list_artifacts(task_id, run_id)
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(
            artifacts[0].logical_path,
            f"/workspace/artifacts/{task_id}/{run_id}/final_response.md",
        )
        artifact, preview = runner.get_artifact_preview(task_id, artifacts[0].artifact_id, run_id)
        self.assertEqual(
            artifact.logical_path, f"/workspace/artifacts/{task_id}/{run_id}/final_response.md"
        )
        self.assertEqual(preview.kind, "markdown")
        self.assertEqual(preview.text, "# Final Response\nImportant execution detail.\n")

    def test_task_runner_keeps_failure_summary_and_registers_failure_artifact(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=FailureWithArtifactHarness(),
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )

        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.FAILED)
        self.assertEqual(snapshot.latest_summary, "Model reported failure.")
        self.assertEqual(snapshot.artifact_count, 1)
        artifacts = runner.list_artifacts(task_id, run_id)
        self.assertEqual(
            artifacts[0].logical_path,
            f"/workspace/artifacts/{task_id}/{run_id}/final_response.md",
        )
        event_types = [event.event.event_type for event in bus.list_events(task_id, run_id)]
        self.assertEqual(
            event_types,
            ["task.created", "task.started", "artifact.created", "task.failed"],
        )

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
            workspace_roots=["/workspace"],
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

    def test_task_runner_resumes_after_transient_upstream_pause(self) -> None:
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
            agent_harness=TransientPauseThenResumeHarness(),
            durable_services=durable_services,
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )

        paused_snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(paused_snapshot.status, TaskStatus.PAUSED)
        self.assertTrue(paused_snapshot.is_resumable)
        self.assertEqual(paused_snapshot.pause_reason, "awaiting resume")
        self.assertEqual(
            paused_snapshot.latest_summary,
            "Execution paused after a transient upstream error. Resume from the latest checkpoint.",
        )

        resumed_snapshot = runner.resume_run(
            task_id,
            run_id,
            identity_bundle_text="identity",
        )
        self.assertEqual(resumed_snapshot.status, TaskStatus.COMPLETED)
        self.assertFalse(resumed_snapshot.is_resumable)
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

    def test_task_runner_replies_and_continues_same_checkpoint_thread(self) -> None:
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
            agent_harness=ClarificationHarness(),
            durable_services=durable_services,
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )

        paused_snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(paused_snapshot.status, TaskStatus.PAUSED)
        self.assertEqual(paused_snapshot.pause_reason, "awaiting_user_input")
        initial_thread_id = paused_snapshot.checkpoint_thread_id

        resumed_snapshot = runner.reply_to_run(
            task_id,
            "Focus on docs only.",
            run_id=run_id,
            identity_bundle_text="identity",
        )

        self.assertEqual(resumed_snapshot.status, TaskStatus.COMPLETED)
        self.assertEqual(resumed_snapshot.checkpoint_thread_id, initial_thread_id)
        event_types = [event.event.event_type for event in bus.list_events(task_id, run_id)]
        self.assertIn("task.user_input_received", event_types)
        messages = durable_services.run_message_store.list_messages(task_id, run_id)
        self.assertEqual(
            [(message.role, message.content) for message in messages],
            [
                (
                    "user",
                    "Inspect the repo\n\nComplete the objective using governed tools and native Deep Agent delegation when it improves focus or isolation.",
                ),
                ("assistant", "Which area should I inspect?"),
                ("user", "Focus on docs only."),
                ("assistant", "Completed after user clarification."),
            ],
        )

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
            workspace_roots=["/workspace"],
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
            workspace_roots=["/workspace"],
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

    def test_task_runner_publishes_memory_updated_events_from_harness(self) -> None:
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
            agent_harness=MemoryWriteHarness(),
            durable_services=durable_services,
        )

        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Create runtime memory",
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )

        events = bus.list_events(task_id, run_id)
        memory_event = next(
            event for event in events if event.event.event_type == EventType.MEMORY_UPDATED.value
        )
        self.assertEqual(memory_event.event.source.kind.value, "memory")
        self.assertEqual(memory_event.event.payload["scope"], "run_state")
        self.assertEqual(memory_event.event.payload["entry_count_delta"], 1)

        entries = durable_services.memory_store.list_memory(scope="run_state")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].namespace, "run.notes")

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
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )

        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.COMPLETED)
        metrics = durable_services.run_metrics_store.read_metrics(task_id, run_id)
        assert metrics is not None
        self.assertEqual(metrics.deny_count, 1)
        self.assertFalse(snapshot.is_resumable)
        self.assertEqual(snapshot.recoverable_rejection_count, 1)
        self.assertIsNotNone(snapshot.last_recoverable_rejection)
        assert snapshot.last_recoverable_rejection is not None
        self.assertIn("network access", snapshot.last_recoverable_rejection.message.lower())
        self.assertIn(
            "tool.rejected",
            [event.event.event_type for event in bus.list_events(task_id, run_id)],
        )

    def test_task_runner_fails_after_recoverable_rejection_threshold(self) -> None:
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
            agent_harness=RepeatedNetworkDeniedHarness(),
            durable_services=durable_services,
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Attempt repeated network access",
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )

        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.FAILED)
        self.assertEqual(snapshot.recoverable_rejection_count, 4)
        self.assertIsNotNone(snapshot.failure)
        assert snapshot.failure is not None
        self.assertEqual(snapshot.failure.code, "recoverable_rejection_threshold_exceeded")
        self.assertIsNotNone(snapshot.last_recoverable_rejection)
        assert snapshot.last_recoverable_rejection is not None
        self.assertEqual(snapshot.last_recoverable_rejection.code, "policy_denied")
        self.assertIn(
            "recoverable_rejection_threshold_exceeded",
            [
                entry.kind
                for entry in durable_services.diagnostic_store.list_diagnostics(task_id, run_id)
            ],
        )
        self.assertEqual(bus.list_events(task_id, run_id)[-1].event.event_type, "task.failed")

    def test_successful_tool_call_resets_recoverable_rejection_streak(self) -> None:
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
            agent_harness=InterleavedNetworkDeniedHarness(),
            durable_services=durable_services,
        )
        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Alternate rejected and successful tool calls",
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )

        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertEqual(snapshot.status, TaskStatus.COMPLETED)
        self.assertEqual(snapshot.recoverable_rejection_count, 0)
        self.assertIsNone(snapshot.last_recoverable_rejection)
        rejection_events = [
            event.event.payload
            for event in bus.list_events(task_id, run_id)
            if event.event.event_type == "tool.rejected"
        ]
        self.assertEqual(len(rejection_events), 3)
        self.assertTrue(all(payload["rejection_count"] == 1 for payload in rejection_events))
        diagnostics = durable_services.diagnostic_store.list_diagnostics(task_id, run_id)
        self.assertNotIn(
            "recoverable_rejection_threshold_exceeded",
            [entry.kind for entry in diagnostics],
        )

    def test_task_runner_passes_phase3_runtime_context_into_harness_request(self) -> None:
        store = InMemoryRunStateStore()
        bus = InMemoryEventBus()
        durable_services = create_durable_runtime_services(
            load_runtime_config("docs/architecture/runtime.example.toml"),
            runtime_root_override=str(self.runtime_root),
        )
        harness = CapturingHarness()
        runner = TaskRunner(
            run_state_store=store,
            event_bus=bus,
            artifact_store=InMemoryArtifactStore(path_mapper=self.sandbox_factory),
            sandbox_factory=self.sandbox_factory,
            agent_harness=harness,
            durable_services=durable_services,
            resolved_subagents=["placeholder"],  # type: ignore[list-item]
        )
        runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )

        assert harness.request is not None
        self.assertEqual(harness.request.resolved_subagents, ["placeholder"])
        self.assertIsNotNone(harness.request.memory_store)
        self.assertEqual(harness.request.artifact_store.__class__.__name__, "InMemoryArtifactStore")

    def test_task_runner_persists_compaction_projection_after_harness_event(self) -> None:
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
            agent_harness=CompactionEventHarness(),
            durable_services=durable_services,
            compaction_policy=CompactionConfig(),
            conversation_compaction_service=ConversationCompactionService(
                run_message_store=durable_services.run_message_store,
                compaction_store=durable_services.conversation_compaction_store,
                strategy=FakeCompactionStrategy(),
            ),
        )

        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )

        snapshot = runner.get_task_snapshot(task_id, run_id)
        self.assertTrue(snapshot.is_compacted)
        self.assertEqual(snapshot.latest_compaction_trigger, "threshold")
        self.assertIsNotNone(snapshot.latest_compaction_id)
        self.assertIn(
            "conversation.compacted",
            [event.event.event_type for event in bus.list_events(task_id, run_id)],
        )
        projected = runner._load_conversation_messages(task_id, run_id)
        self.assertEqual(projected[0]["role"], "user")
        self.assertIn("summary of the conversation", projected[0]["content"].lower())

    def test_task_runner_explicit_compact_updates_projection_and_links(self) -> None:
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
            agent_harness=ClarificationHarness(),
            durable_services=durable_services,
            compaction_policy=CompactionConfig(),
            conversation_compaction_service=ConversationCompactionService(
                run_message_store=durable_services.run_message_store,
                compaction_store=durable_services.conversation_compaction_store,
                strategy=FakeCompactionStrategy(),
            ),
        )

        task_id, run_id, _ = runner.start_run(
            correlation_id="corr_1",
            objective="Inspect the repo",
            workspace_roots=["/workspace"],
            identity_bundle_text="identity",
        )

        paused_snapshot = runner.get_task_snapshot(task_id, run_id)
        assert paused_snapshot.links is not None
        self.assertEqual(paused_snapshot.links["compact"], "task.compact")

        compacted_snapshot = runner.compact_run(task_id, run_id)

        self.assertTrue(compacted_snapshot.is_compacted)
        self.assertEqual(compacted_snapshot.latest_compaction_trigger, "explicit_client")
        projected = runner._load_conversation_messages(task_id, run_id)
        self.assertEqual(projected[0]["role"], "user")
        self.assertIn("summary of the conversation", projected[0]["content"].lower())


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
                    "role": "researcher",
                    "model_profile": "researcher",
                    "objective": "Inspect the repository structure.",
                },
            )
            on_event(
                "subagent.completed",
                {
                    "role": "researcher",
                    "summary": "Researcher finished repository inspection.",
                    "outcome": "success",
                },
            )
            on_event(
                "tool.called",
                {
                    "tool": "write_todos",
                    "arguments": {
                        "todos": [
                            {"content": "Inspect files", "status": "completed"},
                            {"content": "Write summary", "status": "in_progress"},
                        ]
                    },
                    "summary": "Updated todo list (2 items; 1 in progress, 0 pending, 1 completed)",
                    "todo_count": 2,
                    "completed_count": 1,
                    "in_progress_count": 1,
                    "pending_count": 0,
                },
            )
            on_event(
                "tool.called",
                {"tool": "write_file", "path": "/workspace/artifacts/repo_summary.md"},
            )
        request.sandbox.write_text("/workspace/artifacts/repo_summary.md", "# Summary\n")
        return AgentExecutionResult(
            success=True,
            summary="Generated the repository summary artifact.",
            output_artifacts=["/workspace/artifacts/repo_summary.md"],
        )


class RaisingHarness:
    def execute(self, request, on_event=None) -> AgentExecutionResult:
        raise RuntimeError("boom")


class FinalResponseHarness:
    def execute(self, request, on_event=None) -> AgentExecutionResult:
        path = f"/workspace/artifacts/{request.task_id}/{request.run_id}/final_response.md"
        request.sandbox.write_text(path, "# Final Response\nImportant execution detail.\n")
        return AgentExecutionResult(
            success=True,
            summary="Captured final response.",
            output_artifacts=[path],
        )


class FailureWithArtifactHarness:
    def execute(self, request, on_event=None) -> AgentExecutionResult:
        path = f"/workspace/artifacts/{request.task_id}/{request.run_id}/final_response.md"
        request.sandbox.write_text(path, "Model produced a final response before failing.\n")
        return AgentExecutionResult(
            success=False,
            summary="Model reported failure.",
            output_artifacts=[path],
            error_message="model reported failure",
        )


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
        request.sandbox.write_text("/workspace/artifacts/resumed.md", "# Resumed\n")
        return AgentExecutionResult(
            success=True,
            summary="Completed after resume.",
            output_artifacts=["/workspace/artifacts/resumed.md"],
        )


class TransientPauseThenResumeHarness:
    def execute(self, request, on_event=None) -> AgentExecutionResult:
        controller = request.checkpoint_controller
        if controller is None:
            raise AssertionError("checkpoint controller is required for pause/resume tests")
        if request.resume_from_checkpoint_id is None:
            metadata = controller.record_checkpoint("transient_failure")
            if on_event is not None:
                on_event("checkpoint.saved", metadata.to_dict())
            return AgentExecutionResult(
                success=False,
                summary="Execution paused after a transient upstream error. Resume from the latest checkpoint.",
                output_artifacts=[],
                error_message="Internal Server Error (ref: 976bb844-48dc-4d2a-ab25-0de36fbab735) (status code: -1)",
                paused=True,
                pause_reason="awaiting resume",
            )
        metadata = controller.record_checkpoint("resumed")
        if on_event is not None:
            on_event("checkpoint.saved", metadata.to_dict())
        request.sandbox.write_text("/workspace/artifacts/resumed.md", "# Resumed\n")
        return AgentExecutionResult(
            success=True,
            summary="Completed after resume.",
            output_artifacts=["/workspace/artifacts/resumed.md"],
        )


class ClarificationHarness:
    def execute(self, request, on_event=None) -> AgentExecutionResult:
        if len(request.conversation_messages) <= 1:
            return AgentExecutionResult(
                success=False,
                summary="Which area should I inspect?",
                output_artifacts=[],
                paused=True,
                pause_reason="awaiting_user_input",
                requested_user_input="Which area should I inspect?",
            )
        return AgentExecutionResult(
            success=True,
            summary="Completed after user clarification.",
            output_artifacts=[],
            assistant_response="Completed after user clarification.",
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
            artifact_store=request.artifact_store,
            memory_store=request.memory_store,
            on_event=on_event,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=bridge.authorize,
        )
        bindings.write_file("/workspace/apps/runtime/guarded.txt", "content\n")
        return AgentExecutionResult(
            success=True,
            summary="Governed write completed after approval.",
            output_artifacts=[],
        )


class MemoryWriteHarness:
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
            artifact_store=request.artifact_store,
            memory_store=request.memory_store,
            on_event=on_event,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=bridge.authorize,
        )
        bindings.memory_write(
            content="Remember this execution detail.",
            summary="Runtime memory created.",
            namespace="run.notes",
        )
        return AgentExecutionResult(
            success=True,
            summary="Created runtime memory.",
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
            artifact_store=request.artifact_store,
            memory_store=request.memory_store,
            on_event=on_event,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=bridge.authorize,
        )
        bindings.execute_command(["curl", "https://example.com"], cwd="/workspace")
        return AgentExecutionResult(success=True, summary="unexpected", output_artifacts=[])


class RepeatedNetworkDeniedHarness:
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
            artifact_store=request.artifact_store,
            memory_store=request.memory_store,
            on_event=on_event,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=bridge.authorize,
        )
        for _ in range(4):
            bindings.execute_command(["curl", "https://example.com"], cwd="/workspace")
        return AgentExecutionResult(success=True, summary="unexpected", output_artifacts=[])


class InterleavedNetworkDeniedHarness:
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
            artifact_store=request.artifact_store,
            memory_store=request.memory_store,
            on_event=on_event,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=bridge.authorize,
        )
        for _ in range(3):
            bindings.execute_command(["curl", "https://example.com"], cwd="/workspace")
            bindings.list_files("/workspace")
        return AgentExecutionResult(
            success=True,
            summary="Completed after adapting between rejected tool calls.",
            output_artifacts=[],
        )


class CapturingHarness:
    def __init__(self) -> None:
        self.request = None

    def execute(self, request, on_event=None) -> AgentExecutionResult:
        self.request = request
        return AgentExecutionResult(success=True, summary="captured", output_artifacts=[])


class CompactionEventHarness:
    def execute(self, request, on_event=None) -> AgentExecutionResult:
        if on_event is not None:
            on_event(
                "conversation.compacted",
                {
                    "compaction_id": "cmp_runtime",
                    "trigger": "threshold",
                    "strategy": "deepagents_native",
                    "cutoff_index": 1,
                    "summary": "Conversation context compacted during Deep Agent execution.",
                    "created_at": "2026-03-18T12:00:00Z",
                },
            )
        return AgentExecutionResult(
            success=True,
            summary="Completed after compaction.",
            output_artifacts=[],
            assistant_response="Completed after compaction.",
        )


class FakeCompactionStrategy:
    strategy_id = "deepagents_native"

    def build_middleware(self, *, model, policy, on_compaction):
        return []

    def compact_messages(self, *, messages, trigger):
        if len(messages) <= 1:
            return CompactionResult(snapshot=None, projected_messages=list(messages))
        return CompactionResult(
            snapshot=CompactionSnapshot(
                compaction_id="cmp_test",
                trigger=trigger,
                strategy=self.strategy_id,
                cutoff_index=max(1, len(messages) - 1),
                summary_content="Here is a summary of the conversation to date:\n\nSummary",
                created_at="2026-03-18T12:00:00Z",
                provenance={"message_count": len(messages)},
                artifact_path=None,
            ),
            projected_messages=[
                {"role": "user", "content": "Here is a summary of the conversation to date:\n\nSummary"},
                messages[-1],
            ],
        )


if __name__ == "__main__":
    unittest.main()
