from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock, Thread
from typing import Any, Callable, Protocol
from uuid import uuid4

from apps.runtime.local_agent_runtime.subagents import ResolvedSubagentConfiguration
from apps.runtime.local_agent_runtime.subagents import SkillDescriptor
from apps.runtime.local_agent_runtime.artifact_store import ArtifactStore
from apps.runtime.local_agent_runtime.conversation_compaction_service import (
    ConversationCompactionService,
)
from apps.runtime.local_agent_runtime.durable_services import DurableRuntimeServices
from apps.runtime.local_agent_runtime.event_bus import EventBus
from apps.runtime.local_agent_runtime.run_state_store import RunStateStore
from packages.protocol.local_agent_protocol.models import (
    METHOD_TASK_COMPACT,
    ArtifactReference,
    EventEnvelope,
    EventSource,
    EventSourceKind,
    RuntimeEvent,
    TaskSnapshot,
    utc_now_timestamp,
)
from packages.config.local_agent_config.models import CompactionConfig
from packages.task_model.local_agent_task_model.ids import new_event_id, new_run_id, new_task_id
from packages.task_model.local_agent_task_model.models import (
    CompactionTrigger,
    EventType,
    FailureInfo,
    RecoverableToolRejection,
    RecoverableToolRejectionThresholdExceeded,
    RunState,
    TaskStatus,
    TodoItem,
    normalize_todos,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.checkpoint_adapter import (
    CheckpointController,
    LangGraphCheckpointAdapter,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.interrupt_bridge import (
    ApprovalRequiredInterrupt,
    ClarificationRequiredInterrupt,
    PolicyDeniedInterrupt,
)
from services.observability_service.local_agent_observability_service.observability_models import (
    RunMessageRecord,
    RunMetricsRecord,
)
from services.policy_service.local_agent_policy_service.boundary_scope import BoundaryGrant
from services.policy_service.local_agent_policy_service.policy_models import (
    ApprovalRequest,
    OperationContext,
    PolicyDecision,
)
from services.memory_service.local_agent_memory_service.memory_store import MemoryStore
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    ExecutionSandbox,
    LocalExecutionSandboxFactory,
)
from services.subagent_runtime.local_agent_subagent_runtime import (
    RuntimeSkillCatalog,
    SkillInstallationService,
    SkillInstallOutcome,
    SkillValidationFinding,
    SkillValidationResult,
)


@dataclass(slots=True)
class AgentExecutionRequest:
    task_id: str
    run_id: str
    objective: str
    workspace_roots: list[str]
    identity_bundle_text: str
    sandbox: ExecutionSandbox
    resolved_subagents: list[ResolvedSubagentConfiguration]
    artifact_store: ArtifactStore
    memory_store: MemoryStore | None
    allowed_capabilities: list[str]
    metadata: dict[str, Any]
    conversation_messages: tuple[dict[str, str], ...] = ()
    primary_skills: tuple[SkillDescriptor, ...] = ()
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    checkpoint_controller: CheckpointController | None = None
    resume_from_checkpoint_id: str | None = None
    governed_operation: Callable[[OperationContext], None] | None = None
    skill_install_handler: Callable[..., dict[str, Any]] | None = None


@dataclass(slots=True)
class AgentExecutionResult:
    success: bool
    summary: str
    output_artifacts: list[str]
    error_message: str | None = None
    paused: bool = False
    pause_reason: str | None = None
    awaiting_approval: bool = False
    pending_approval_id: str | None = None
    failure_code: str | None = None
    requested_user_input: str | None = None
    assistant_response: str | None = None


_RECOVERABLE_TOOL_REJECTION_THRESHOLD = 3


class AgentHarness(Protocol):
    def execute(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> AgentExecutionResult: ...


class StubAgentHarness:
    def __init__(
        self,
        *,
        success: bool = True,
        summary: str | None = None,
        output_artifact_path: str | None = None,
        output_artifact_content: str = "# Runtime Artifact\n",
    ) -> None:
        self._success = success
        self._summary = summary
        self._output_artifact_path = output_artifact_path
        self._output_artifact_content = output_artifact_content

    def execute(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> AgentExecutionResult:
        if self._success:
            output_artifacts: list[str] = []
            if self._output_artifact_path is not None:
                request.sandbox.write_text(
                    self._output_artifact_path, self._output_artifact_content
                )
                output_artifacts.append(request.sandbox.normalize_path(self._output_artifact_path))
            summary = self._summary or "Stub harness completed without external execution."
            return AgentExecutionResult(
                success=True,
                summary=summary,
                output_artifacts=output_artifacts,
            )
        summary = self._summary or "Stub harness failed before external execution."
        return AgentExecutionResult(
            success=False,
            summary=summary,
            output_artifacts=[],
            error_message="stub harness failure",
        )


class TaskRunner:
    def __init__(
        self,
        run_state_store: RunStateStore,
        event_bus: EventBus,
        artifact_store: ArtifactStore,
        sandbox_factory: LocalExecutionSandboxFactory,
        agent_harness: AgentHarness,
        durable_services: DurableRuntimeServices | None = None,
        resolved_subagents: list[ResolvedSubagentConfiguration] | None = None,
        primary_skills: tuple[SkillDescriptor, ...] = (),
        skill_catalog: RuntimeSkillCatalog | None = None,
        compaction_policy: CompactionConfig | None = None,
        conversation_compaction_service: ConversationCompactionService | None = None,
    ) -> None:
        self._run_state_store = run_state_store
        self._event_bus = event_bus
        self._artifact_store = artifact_store
        self._sandbox_factory = sandbox_factory
        self._agent_harness = agent_harness
        self._durable_services = durable_services
        self._resolved_subagents = list(resolved_subagents or [])
        self._primary_skills = tuple(primary_skills)
        self._skill_catalog = skill_catalog
        self._compaction_policy = compaction_policy or CompactionConfig()
        self._skill_installer = (
            SkillInstallationService(skill_catalog) if skill_catalog is not None else None
        )
        self._source = EventSource(kind=EventSourceKind.RUNTIME, component="task-runner")
        self._checkpoint_adapter = (
            LangGraphCheckpointAdapter(durable_services.checkpoint_store)
            if durable_services is not None
            else None
        )
        self._run_threads: dict[tuple[str, str], Thread] = {}
        self._thread_lock = RLock()
        self._rehydrated_artifact_runs: set[tuple[str, str]] = set()
        self._conversation_compaction_service = conversation_compaction_service

    @property
    def resolved_subagents(self) -> list[ResolvedSubagentConfiguration]:
        if self._skill_catalog is not None:
            return self._skill_catalog.resolve_subagents()
        return list(self._resolved_subagents)

    @property
    def primary_skills(self) -> tuple[SkillDescriptor, ...]:
        if self._skill_catalog is not None:
            return self._skill_catalog.load_primary_skills()
        return self._primary_skills

    def start_run(
        self,
        correlation_id: str | None,
        objective: str,
        workspace_roots: list[str],
        identity_bundle_text: str,
        allowed_capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        constraints: list[str] | None = None,
        success_criteria: list[str] | None = None,
        background: bool = False,
    ) -> tuple[str, str, str]:
        normalized_workspace_roots = self._sandbox_factory.normalize_workspace_roots(
            workspace_roots
        )
        task_id = new_task_id()
        run_id = new_run_id()
        accepted_at = utc_now_timestamp()
        state = RunState(
            task_id=task_id,
            run_id=run_id,
            status=TaskStatus.ACCEPTED,
            objective=objective,
            created_at=accepted_at,
            updated_at=accepted_at,
            accepted_at=accepted_at,
            workspace_roots=list(normalized_workspace_roots),
            allowed_capabilities=list(allowed_capabilities or []),
            metadata=dict(metadata or {}),
            constraints=list(constraints or []),
            success_criteria=list(success_criteria or []),
            current_phase="accepted",
            latest_summary="Task accepted by runtime.",
            awaiting_approval=False,
            is_resumable=False,
            checkpoint_thread_id=self._new_checkpoint_thread(task_id, run_id),
            links={
                "artifacts": "task.artifacts.list",
                "approve": "task.approve",
                "reply": "task.reply",
                "resume": "task.resume",
                "events": "task.logs.stream",
            },
        )
        self._run_state_store.create(state)
        self._write_metrics(task_id, run_id, started_at=accepted_at)
        self._seed_run_message_history(
            task_id=task_id,
            run_id=run_id,
            objective=objective,
            constraints=state.constraints,
            success_criteria=state.success_criteria,
        )
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.TASK_CREATED.value,
            timestamp=accepted_at,
            source=self._source,
            payload={
                "status": TaskStatus.CREATED.value,
                "objective": objective,
                "workspace_roots": list(normalized_workspace_roots),
                "allowed_capabilities": list(allowed_capabilities or []),
                "metadata": dict(metadata or {}),
                "constraints": list(constraints or []),
                "success_criteria": list(success_criteria or []),
            },
        )
        self._launch_run(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            identity_bundle_text=identity_bundle_text,
            resume=False,
            background=background,
        )

        return task_id, run_id, accepted_at

    def resume_run(
        self,
        task_id: str,
        run_id: str | None = None,
        *,
        identity_bundle_text: str,
        background: bool = False,
    ) -> TaskSnapshot:
        state = self._run_state_store.get(task_id, run_id)
        if state.status == TaskStatus.COMPLETED:
            raise ValueError("task.resume cannot resume a completed run")
        if state.status == TaskStatus.FAILED:
            raise ValueError("task.resume cannot resume a failed run")
        if state.awaiting_approval:
            raise ValueError("task.resume cannot resume while approval is still pending")
        if not state.is_resumable:
            raise ValueError("task.resume requires a paused or resumable run")
        self._launch_run(
            task_id=state.task_id,
            run_id=state.run_id,
            correlation_id=None,
            identity_bundle_text=identity_bundle_text,
            resume=True,
            background=background,
        )
        return self.get_task_snapshot(state.task_id, state.run_id)

    def reply_to_run(
        self,
        task_id: str,
        message: str,
        *,
        run_id: str | None,
        identity_bundle_text: str,
        background: bool = False,
    ) -> TaskSnapshot:
        state = self._run_state_store.get(task_id, run_id)
        if state.status == TaskStatus.COMPLETED:
            raise ValueError("task.reply cannot reply to a completed run")
        if state.status == TaskStatus.FAILED:
            raise ValueError("task.reply cannot reply to a failed run")
        if state.awaiting_approval:
            raise ValueError("task.reply cannot reply while approval is still pending")
        if not state.is_resumable:
            raise ValueError("task.reply requires a paused or resumable run")
        if state.pause_reason != "awaiting_user_input":
            raise ValueError("task.reply requires a run paused for awaiting_user_input")
        now = utc_now_timestamp()
        self._append_run_message(
            task_id=state.task_id,
            run_id=state.run_id,
            role="user",
            content=message,
            created_at=now,
        )
        self._publish(
            task_id=state.task_id,
            run_id=state.run_id,
            correlation_id=None,
            event_type=EventType.TASK_USER_INPUT_RECEIVED.value,
            timestamp=now,
            source=self._source,
            payload={
                "status": TaskStatus.PAUSED.value,
                "summary": "User input received. Resuming execution.",
                "message": message,
            },
        )
        self._launch_run(
            task_id=state.task_id,
            run_id=state.run_id,
            correlation_id=None,
            identity_bundle_text=identity_bundle_text,
            resume=True,
            background=background,
        )
        return self.get_task_snapshot(state.task_id, state.run_id)

    def approve(
        self,
        task_id: str | None,
        approval_id: str,
        decision: str,
        *,
        run_id: str | None,
        identity_bundle_text: str,
    ) -> tuple[str, bool, str, TaskSnapshot]:
        if self._durable_services is None:
            raise ValueError("task.approve requires durable runtime services")
        request = self._durable_services.approval_store.get_request(approval_id)
        if request is None:
            raise KeyError(f"unknown approval: {approval_id}")
        if task_id is not None and request.task_id != task_id:
            raise ValueError("approval does not belong to the requested task")
        if run_id is not None and request.run_id != run_id:
            raise ValueError("approval does not belong to the requested run")

        state = self._run_state_store.get(request.task_id, request.run_id)
        is_direct_skill_install = request.scope.get("kind") == "skill.install"
        if not is_direct_skill_install and state.pending_approval_id != approval_id:
            raise ValueError("approval is not the active pending approval for this run")

        decided = self._durable_services.approval_store.decide(
            approval_id,
            decision,
            utc_now_timestamp(),
        )
        decision_at = utc_now_timestamp()
        self._run_state_store.update(
            state.task_id,
            state.run_id,
            updated_at=decision_at,
            awaiting_approval=False,
            pending_approval_id=None,
        )

        if decided.status == "approved":
            if is_direct_skill_install:
                self._approve_skill_install(request, correlation_id=None)
                return (
                    approval_id,
                    True,
                    decided.status,
                    self.get_task_snapshot(state.task_id, state.run_id),
                )
            boundary_key = decided.scope.get("boundary_key")
            if isinstance(boundary_key, str) and boundary_key:
                self._durable_services.boundary_grant_store.grant(
                    BoundaryGrant(
                        task_id=state.task_id,
                        run_id=state.run_id,
                        boundary_key=boundary_key,
                        approval_id=approval_id,
                        granted_at=decision_at,
                    )
                )
            snapshot = self.resume_run(
                state.task_id,
                state.run_id,
                identity_bundle_text=identity_bundle_text,
            )
            return approval_id, True, decided.status, snapshot

        if is_direct_skill_install:
            self._append_diagnostic(
                task_id=state.task_id,
                run_id=state.run_id,
                kind="skill_install_approval_rejected",
                message="Skill installation approval was rejected by the user.",
                details={"approval_id": approval_id, "scope": decided.scope},
            )
            self._publish_skill_install_event(
                task_id=state.task_id,
                run_id=state.run_id,
                correlation_id=None,
                event_type=EventType.SKILL_INSTALL_FAILED.value,
                payload={
                    "summary": "Skill installation approval was rejected.",
                    "approval_id": approval_id,
                },
            )
            return (
                approval_id,
                False,
                decided.status,
                self.get_task_snapshot(state.task_id, state.run_id),
            )

        self._append_diagnostic(
            task_id=state.task_id,
            run_id=state.run_id,
            kind="approval_rejected",
            message="Approval was rejected by the user.",
            details={"approval_id": approval_id, "scope": decided.scope},
        )
        self._run_state_store.update(
            state.task_id,
            state.run_id,
            status=TaskStatus.FAILED,
            updated_at=decision_at,
            current_phase="failed",
            latest_summary="Run failed because the required approval was rejected.",
            last_event_at=decision_at,
            failure=FailureInfo(message="approval rejected", code="approval_rejected"),
            awaiting_approval=False,
            pending_approval_id=None,
            is_resumable=False,
            pause_reason=None,
        )
        self._publish(
            task_id=state.task_id,
            run_id=state.run_id,
            correlation_id=None,
            event_type=EventType.TASK_FAILED.value,
            timestamp=decision_at,
            source=self._source,
            payload={
                "status": TaskStatus.FAILED.value,
                "failed_at": decision_at,
                "summary": "Run failed because the required approval was rejected.",
                "error": "approval rejected",
            },
        )
        return (
            approval_id,
            False,
            decided.status,
            self.get_task_snapshot(state.task_id, state.run_id),
        )

    def skill_install(
        self,
        *,
        correlation_id: str | None,
        task_id: str,
        run_id: str | None,
        source_path: str,
        target_scope: str,
        target_role: str | None,
        install_mode: str,
        reason: str,
    ) -> SkillInstallOutcome:
        if self._skill_installer is None:
            raise ValueError("skill.install requires runtime skill catalog support")
        state = self._run_state_store.get(task_id, run_id)
        sandbox = self._sandbox_factory.for_run(
            task_id=state.task_id,
            run_id=state.run_id,
            workspace_roots=state.workspace_roots,
        )
        return self._install_skill_via_runtime_method(
            correlation_id=correlation_id,
            task_id=state.task_id,
            run_id=state.run_id,
            sandbox=sandbox,
            source_path=source_path,
            target_scope=target_scope,
            target_role=target_role,
            install_mode=install_mode,
            reason=reason,
        )

    def get_task_snapshot(self, task_id: str, run_id: str | None = None) -> TaskSnapshot:
        state = self._run_state_store.get(task_id, run_id)
        latest_compaction = (
            None
            if self._conversation_compaction_service is None
            else self._conversation_compaction_service.latest_snapshot(state.task_id, state.run_id)
        )
        links = dict(state.links)
        if self._allows_explicit_compaction(state):
            links["compact"] = METHOD_TASK_COMPACT
        else:
            links.pop("compact", None)
        return TaskSnapshot(
            task_id=state.task_id,
            run_id=state.run_id,
            status=state.status,
            objective=state.objective,
            created_at=state.created_at,
            updated_at=state.updated_at,
            success_criteria=state.success_criteria or None,
            constraints=state.constraints or None,
            workspace_roots=state.workspace_roots or None,
            current_phase=state.current_phase,
            latest_summary=state.latest_summary,
            todos=list(state.todos) or None,
            awaiting_approval=state.awaiting_approval,
            pending_approval_id=state.pending_approval_id,
            is_resumable=state.is_resumable,
            pause_reason=state.pause_reason,
            checkpoint_thread_id=state.checkpoint_thread_id,
            latest_checkpoint_id=state.latest_checkpoint_id,
            is_compacted=latest_compaction is not None,
            latest_compaction_id=(
                latest_compaction.compaction_id if latest_compaction is not None else None
            ),
            latest_compaction_trigger=(
                latest_compaction.trigger if latest_compaction is not None else None
            ),
            active_subagent=state.active_subagent,
            artifact_count=state.artifact_count,
            recoverable_rejection_count=state.recoverable_rejection_count,
            last_event_at=state.last_event_at,
            failure=state.failure,
            last_recoverable_rejection=state.last_recoverable_rejection,
            links=links or None,
        )

    def compact_run(self, task_id: str, run_id: str | None = None) -> TaskSnapshot:
        state = self._run_state_store.get(task_id, run_id)
        if not self._allows_explicit_compaction(state):
            raise ValueError("task.compact requires an accepted, paused, or resumable run")
        record = self._persist_compaction_projection(
            task_id=state.task_id,
            run_id=state.run_id,
            trigger=CompactionTrigger.EXPLICIT_CLIENT,
        )
        if record is not None:
            now = utc_now_timestamp()
            self._publish(
                task_id=state.task_id,
                run_id=state.run_id,
                correlation_id=None,
                event_type=EventType.CONVERSATION_COMPACTED.value,
                timestamp=now,
                source=self._source,
                payload={
                    "compaction_id": record.compaction_id,
                    "trigger": record.trigger,
                    "strategy": record.strategy,
                    "cutoff_index": record.cutoff_index,
                    "summary": "Conversation context compacted.",
                    "created_at": record.created_at,
                    "artifact_path": record.artifact_path,
                },
            )
        return self.get_task_snapshot(state.task_id, state.run_id)

    def list_artifacts(
        self,
        task_id: str,
        run_id: str | None = None,
        persistence_class: str | None = None,
        content_type_prefix: str | None = None,
    ) -> list:
        resolved_run_id = self._run_state_store.get(task_id, run_id).run_id
        self._ensure_artifacts_loaded(task_id, resolved_run_id)
        return self._artifact_store.list_artifacts(
            task_id,
            resolved_run_id,
            persistence_class=persistence_class,
            content_type_prefix=content_type_prefix,
        )

    def get_artifact_preview(
        self,
        task_id: str,
        artifact_id: str,
        run_id: str | None = None,
    ) -> tuple:
        resolved_run_id = self._run_state_store.get(task_id, run_id).run_id
        self._ensure_artifacts_loaded(task_id, resolved_run_id)
        return self._artifact_store.get_artifact_preview(task_id, artifact_id, resolved_run_id)

    @property
    def checkpoint_adapter(self) -> LangGraphCheckpointAdapter | None:
        return self._checkpoint_adapter

    def wait_for_all_runs(self) -> None:
        while True:
            with self._thread_lock:
                threads = list(self._run_threads.values())
            if not threads:
                return
            for thread in threads:
                thread.join()

    def _launch_run(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        identity_bundle_text: str,
        resume: bool,
        background: bool,
    ) -> None:
        if not background:
            self._execute_run(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                identity_bundle_text=identity_bundle_text,
                resume=resume,
            )
            return

        key = (task_id, run_id)
        worker = Thread(
            target=self._execute_run_in_thread,
            name=f"task-runner-{task_id}-{run_id}",
            kwargs={
                "task_id": task_id,
                "run_id": run_id,
                "correlation_id": correlation_id,
                "identity_bundle_text": identity_bundle_text,
                "resume": resume,
            },
        )
        with self._thread_lock:
            self._run_threads[key] = worker
        worker.start()

    def _execute_run_in_thread(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        identity_bundle_text: str,
        resume: bool,
    ) -> None:
        try:
            self._execute_run(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                identity_bundle_text=identity_bundle_text,
                resume=resume,
            )
        finally:
            with self._thread_lock:
                self._run_threads.pop((task_id, run_id), None)

    def _execute_run(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        identity_bundle_text: str,
        resume: bool,
    ) -> None:
        state = self._run_state_store.get(task_id, run_id)
        started_at = utc_now_timestamp()
        checkpoint_controller = self._checkpoint_controller_for_run(task_id, run_id, resume)
        self._run_state_store.update(
            task_id,
            run_id,
            status=TaskStatus.EXECUTING,
            updated_at=started_at,
            current_phase="executing",
            latest_summary="Agent harness execution started."
            if not resume
            else "Runtime resumed execution from the latest checkpoint metadata.",
            last_event_at=started_at,
            awaiting_approval=False,
            is_resumable=False,
            pause_reason=None,
            checkpoint_thread_id=(
                checkpoint_controller.thread_id
                if checkpoint_controller is not None
                else state.checkpoint_thread_id
            ),
            latest_checkpoint_id=(
                checkpoint_controller.latest_checkpoint_id
                if checkpoint_controller is not None
                else state.latest_checkpoint_id
            ),
            active_subagent=None,
        )
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.TASK_RESUMED.value if resume else EventType.TASK_STARTED.value,
            timestamp=started_at,
            source=self._source,
            payload={
                "status": TaskStatus.EXECUTING.value,
                "started_at": started_at,
                "thread_id": checkpoint_controller.thread_id
                if checkpoint_controller is not None
                else None,
                "latest_checkpoint_id": (
                    checkpoint_controller.latest_checkpoint_id
                    if checkpoint_controller is not None
                    else state.latest_checkpoint_id
                ),
                "summary": (
                    "Execution resumed from the latest checkpoint."
                    if resume
                    else "Agent harness execution started."
                ),
            },
        )
        if resume:
            self._increment_resume_metrics(task_id, run_id)

        sandbox = self._sandbox_factory.for_run(
            task_id=task_id,
            run_id=run_id,
            workspace_roots=state.workspace_roots,
        )
        compaction_triggers: list[CompactionTrigger] = []

        def _on_harness_event(event_type: str, payload: dict[str, Any]) -> None:
            if event_type == EventType.CONVERSATION_COMPACTED.value:
                trigger_name = payload.get("trigger")
                if isinstance(trigger_name, str):
                    try:
                        compaction_triggers.append(CompactionTrigger(trigger_name))
                    except ValueError:
                        pass
            self._handle_harness_event(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                event_type=event_type,
                payload=payload,
            )

        try:
            conversation_messages = tuple(self._load_conversation_messages(task_id, run_id))
            result = self._agent_harness.execute(
                AgentExecutionRequest(
                    task_id=task_id,
                    run_id=run_id,
                    objective=state.objective,
                    workspace_roots=list(state.workspace_roots),
                    identity_bundle_text=identity_bundle_text,
                    sandbox=sandbox,
                    resolved_subagents=self.resolved_subagents,
                    artifact_store=self._artifact_store,
                    memory_store=(
                        self._durable_services.memory_store
                        if self._durable_services is not None
                        else None
                    ),
                    allowed_capabilities=list(state.allowed_capabilities),
                    metadata=dict(state.metadata),
                    conversation_messages=conversation_messages,
                    primary_skills=self.primary_skills,
                    constraints=list(state.constraints),
                    success_criteria=list(state.success_criteria),
                    checkpoint_controller=checkpoint_controller,
                    resume_from_checkpoint_id=(
                        checkpoint_controller.latest_checkpoint_id
                        if checkpoint_controller is not None
                        else None
                    ),
                    governed_operation=lambda context: self._govern_operation(
                        correlation_id=correlation_id,
                        context=context,
                    ),
                    skill_install_handler=lambda **kwargs: self._install_skill_via_tool(
                        correlation_id=correlation_id,
                        task_id=task_id,
                        run_id=run_id,
                        sandbox=sandbox,
                        **kwargs,
                    ).to_dict(),
                ),
                on_event=_on_harness_event,
            )
        except ApprovalRequiredInterrupt as exc:
            result = AgentExecutionResult(
                success=False,
                summary=exc.summary,
                output_artifacts=[],
                paused=True,
                pause_reason="awaiting approval",
                awaiting_approval=True,
                pending_approval_id=exc.approval_id,
            )
        except ClarificationRequiredInterrupt as exc:
            result = AgentExecutionResult(
                success=False,
                summary=exc.question,
                output_artifacts=[],
                paused=True,
                pause_reason="awaiting_user_input",
                requested_user_input=exc.question,
            )
        except PolicyDeniedInterrupt as exc:
            result = AgentExecutionResult(
                success=False,
                summary=exc.reason,
                output_artifacts=[],
                error_message=exc.reason,
                failure_code="policy_denied",
            )
        except RecoverableToolRejectionThresholdExceeded as exc:
            result = AgentExecutionResult(
                success=False,
                summary=exc.summary,
                output_artifacts=[],
                error_message=str(exc),
                failure_code="recoverable_rejection_threshold_exceeded",
            )
        except Exception as exc:
            self._append_diagnostic(
                task_id=task_id,
                run_id=run_id,
                kind="agent_harness_error",
                message=str(exc),
                details={"phase": "execute", "resume": resume},
            )
            result = AgentExecutionResult(
                success=False,
                summary="Agent harness raised an unexpected error.",
                output_artifacts=[],
                error_message=str(exc),
            )

        artifact_count = state.artifact_count
        assistant_response = result.requested_user_input or result.assistant_response
        if assistant_response:
            self._append_run_message(
                task_id=task_id,
                run_id=run_id,
                role="assistant",
                content=assistant_response,
            )
        if compaction_triggers:
            self._persist_compaction_projection(
                task_id=task_id,
                run_id=run_id,
                trigger=compaction_triggers[-1],
            )
        for sandbox_path in result.output_artifacts:
            artifact = self._artifact_store.register_artifact(
                task_id=task_id,
                run_id=run_id,
                sandbox_path=sandbox_path,
            )
            artifact_count += 1
            registered_at = utc_now_timestamp()
            self._run_state_store.update(
                task_id,
                run_id,
                updated_at=registered_at,
                artifact_count=artifact_count,
                last_event_at=registered_at,
            )
            self._publish(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                event_type=EventType.ARTIFACT_CREATED.value,
                timestamp=registered_at,
                source=EventSource(kind=EventSourceKind.RUNTIME, component="artifact-store"),
                payload={"artifact": artifact.to_dict()},
            )
            self._write_metrics(task_id, run_id, artifact_count=artifact_count)

        if result.paused:
            paused_at = utc_now_timestamp()
            if result.awaiting_approval:
                self._run_state_store.update(
                    task_id,
                    run_id,
                    status=TaskStatus.AWAITING_APPROVAL,
                    updated_at=paused_at,
                    current_phase="awaiting_approval",
                    latest_summary=result.summary,
                    artifact_count=artifact_count,
                    last_event_at=paused_at,
                    awaiting_approval=True,
                    pending_approval_id=result.pending_approval_id,
                    is_resumable=True,
                    pause_reason=result.pause_reason or "awaiting approval",
                    active_subagent=None,
                )
            else:
                self._run_state_store.update(
                    task_id,
                    run_id,
                    status=TaskStatus.PAUSED,
                    updated_at=paused_at,
                    current_phase="paused",
                    latest_summary=result.summary,
                    artifact_count=artifact_count,
                    last_event_at=paused_at,
                    is_resumable=True,
                    pause_reason=result.pause_reason or "execution paused",
                    active_subagent=None,
                )
                self._publish(
                    task_id=task_id,
                    run_id=run_id,
                    correlation_id=correlation_id,
                    event_type=EventType.TASK_PAUSED.value,
                    timestamp=paused_at,
                    source=self._source,
                    payload={
                        "status": TaskStatus.PAUSED.value,
                        "reason": result.pause_reason or "execution paused",
                        "summary": result.summary,
                        "question": result.requested_user_input,
                    },
                )
            self._write_metrics(task_id, run_id, artifact_count=artifact_count)
            return

        if result.success:
            completed_at = utc_now_timestamp()
            self._run_state_store.update(
                task_id,
                run_id,
                status=TaskStatus.COMPLETED,
                updated_at=completed_at,
                current_phase="completed",
                latest_summary=result.summary,
                artifact_count=artifact_count,
                last_event_at=completed_at,
                is_resumable=False,
                pause_reason=None,
                active_subagent=None,
            )
            self._publish(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                event_type=EventType.TASK_COMPLETED.value,
                timestamp=completed_at,
                source=self._source,
                payload={
                    "status": TaskStatus.COMPLETED.value,
                    "completed_at": completed_at,
                    "summary": result.summary,
                    "outcome": "success",
                    "artifact_count": artifact_count,
                },
            )
            self._write_metrics(
                task_id,
                run_id,
                ended_at=completed_at,
                artifact_count=artifact_count,
            )
            return

        failed_at = utc_now_timestamp()
        if result.failure_code == "scope_denied":
            self._append_diagnostic(
                task_id=task_id,
                run_id=run_id,
                kind="filesystem_scope_denied",
                message=result.error_message or result.summary,
                details={"summary": result.summary, "resume": resume},
            )
            self._publish(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                event_type=EventType.POLICY_DENIED.value,
                timestamp=failed_at,
                source=EventSource(kind=EventSourceKind.POLICY, component="filesystem-scope"),
                payload={
                    "status": TaskStatus.FAILED.value,
                    "reason": result.error_message or result.summary,
                    "context": {"kind": "filesystem_scope"},
                },
            )
        elif result.failure_code != "policy_denied":
            self._append_diagnostic(
                task_id=task_id,
                run_id=run_id,
                kind="task_failure",
                message=result.error_message or result.summary,
                details={"summary": result.summary, "resume": resume},
            )
        self._run_state_store.update(
            task_id,
            run_id,
            status=TaskStatus.FAILED,
            updated_at=failed_at,
            current_phase="failed",
            latest_summary=result.summary,
            artifact_count=artifact_count,
            last_event_at=failed_at,
            failure=FailureInfo(
                message=result.error_message or result.summary,
                code=result.failure_code,
            ),
            awaiting_approval=False,
            pending_approval_id=None,
            is_resumable=False,
            pause_reason=None,
            active_subagent=None,
        )
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.TASK_FAILED.value,
            timestamp=failed_at,
            source=self._source,
            payload={
                "status": TaskStatus.FAILED.value,
                "failed_at": failed_at,
                "summary": result.summary,
                "error": result.error_message or result.summary,
            },
        )
        self._write_metrics(task_id, run_id, ended_at=failed_at, artifact_count=artifact_count)

    def _publish(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        event_type: str,
        timestamp: str,
        source: EventSource,
        payload: dict[str, Any],
    ) -> None:
        runtime_event = RuntimeEvent(
            event=EventEnvelope(
                event_id=new_event_id(),
                event_type=event_type,
                timestamp=timestamp,
                correlation_id=correlation_id,
                task_id=task_id,
                run_id=run_id,
                source=source,
                payload=payload,
            )
        )
        self._event_bus.publish(runtime_event)
        if self._durable_services is not None:
            self._durable_services.event_store.append_event(runtime_event.event)
        self._write_metrics(task_id, run_id, event_count_increment=1)

    def _handle_harness_event(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        timestamp = utc_now_timestamp()
        if event_type == EventType.TOOL_REJECTED.value:
            self._record_recoverable_tool_rejection(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                timestamp=timestamp,
                payload=payload,
            )
            return
        if event_type == EventType.TOOL_CALLED.value:
            self._reset_recoverable_tool_rejection_streak(
                task_id=task_id,
                run_id=run_id,
                timestamp=timestamp,
            )
        updates: dict[str, Any] = {
            "updated_at": timestamp,
            "last_event_at": timestamp,
        }
        phase = payload.get("phase")
        if isinstance(phase, str) and phase.strip():
            updates["current_phase"] = phase.strip()
        elif event_type == EventType.PLAN_UPDATED.value:
            updates["current_phase"] = "planning"
        elif event_type == EventType.SUBAGENT_STARTED.value:
            updates["current_phase"] = "executing"
            role = payload.get("subagentId")
            if isinstance(role, str) and role.strip():
                updates["active_subagent"] = role.strip()
        elif event_type == EventType.SUBAGENT_COMPLETED.value:
            updates["current_phase"] = "executing"
            updates["active_subagent"] = None
        summary = payload.get("summary")
        if isinstance(summary, str) and summary.strip():
            updates["latest_summary"] = summary.strip()
        todos = _todos_from_event_payload(payload)
        if todos is not None:
            updates["todos"] = todos
        if event_type == EventType.CHECKPOINT_SAVED.value:
            checkpoint_id = payload.get("checkpoint_id")
            thread_id = payload.get("thread_id")
            if isinstance(checkpoint_id, str) and checkpoint_id.strip():
                updates["latest_checkpoint_id"] = checkpoint_id
                updates["is_resumable"] = True
            if isinstance(thread_id, str) and thread_id.strip():
                updates["checkpoint_thread_id"] = thread_id
            self._increment_checkpoint_metrics(task_id, run_id)
        self._run_state_store.update(task_id, run_id, **updates)
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=event_type,
            timestamp=timestamp,
            source=_source_for_harness_event(event_type, payload),
            payload=payload,
        )

    def _append_diagnostic(
        self,
        *,
        task_id: str,
        run_id: str,
        kind: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        if self._durable_services is None:
            return
        self._durable_services.diagnostic_store.append_diagnostic(
            task_id=task_id,
            run_id=run_id,
            kind=kind,
            message=message,
            details=details or {},
        )

    def _govern_operation(
        self,
        *,
        correlation_id: str | None,
        context: OperationContext,
    ) -> None:
        if self._durable_services is None:
            return
        decision = self._durable_services.policy_engine.evaluate(context)
        if decision.decision == "ALLOW":
            return
        if decision.decision == "DENY":
            raise RecoverableToolRejection(
                code="policy_denied",
                message=decision.reason,
                category="policy_denied",
                details={"context": context.to_dict()},
            )
        approval = self._create_approval_request(
            correlation_id=correlation_id,
            context=context,
            decision=decision,
        )
        raise ApprovalRequiredInterrupt(
            approval_id=approval.approval_id,
            summary=approval.description,
        )

    def _record_recoverable_tool_rejection(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        timestamp: str,
        payload: dict[str, Any],
    ) -> None:
        state = self._run_state_store.get(task_id, run_id)
        rejection_count = state.recoverable_rejection_count + 1
        code = _str_or_none(payload.get("code"))
        message = _str_or_none(payload.get("message")) or "Tool rejected by runtime."
        tool_name = _str_or_none(payload.get("tool")) or "tool"
        summary = _str_or_none(payload.get("summary")) or f"{tool_name} rejected: {message}"
        payload["rejection_count"] = rejection_count
        payload["threshold"] = _RECOVERABLE_TOOL_REJECTION_THRESHOLD
        payload["summary"] = summary

        self._append_diagnostic(
            task_id=task_id,
            run_id=run_id,
            kind="tool_rejected",
            message=message,
            details={
                "tool": tool_name,
                "code": code,
                "category": payload.get("category"),
                "retryable": payload.get("retryable", True),
                "arguments": payload.get("arguments", {}),
                "details": payload.get("details", {}),
            },
        )
        self._run_state_store.update(
            task_id,
            run_id,
            updated_at=timestamp,
            last_event_at=timestamp,
            latest_summary=summary,
            recoverable_rejection_count=rejection_count,
            last_recoverable_rejection=FailureInfo(message=message, code=code),
        )
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.TOOL_REJECTED.value,
            timestamp=timestamp,
            source=_source_for_harness_event(EventType.TOOL_REJECTED.value, payload),
            payload=payload,
        )
        if payload.get("category") == "policy_denied":
            self._write_metrics(task_id, run_id, deny_count_increment=1)
        if rejection_count > _RECOVERABLE_TOOL_REJECTION_THRESHOLD:
            self._append_diagnostic(
                task_id=task_id,
                run_id=run_id,
                kind="recoverable_rejection_threshold_exceeded",
                message=summary,
                details={
                    "rejection_count": rejection_count,
                    "threshold": _RECOVERABLE_TOOL_REJECTION_THRESHOLD,
                    "tool": tool_name,
                    "code": code,
                },
            )
            raise RecoverableToolRejectionThresholdExceeded(
                threshold=_RECOVERABLE_TOOL_REJECTION_THRESHOLD,
                rejection_count=rejection_count,
                last_rejection=FailureInfo(message=message, code=code),
            )

    def _reset_recoverable_tool_rejection_streak(
        self,
        *,
        task_id: str,
        run_id: str,
        timestamp: str,
    ) -> None:
        state = self._run_state_store.get(task_id, run_id)
        if (
            state.recoverable_rejection_count == 0
            and state.last_recoverable_rejection is None
        ):
            return
        self._run_state_store.update(
            task_id,
            run_id,
            updated_at=timestamp,
            recoverable_rejection_count=0,
            last_recoverable_rejection=None,
        )

    def _create_approval_request(
        self,
        *,
        correlation_id: str | None,
        context: OperationContext,
        decision: PolicyDecision,
    ) -> ApprovalRequest:
        assert self._durable_services is not None
        now = utc_now_timestamp()
        approval = ApprovalRequest(
            approval_id=f"approval_{uuid4().hex[:12]}",
            task_id=context.task_id,
            run_id=context.run_id,
            type="boundary",
            scope={
                **(decision.approval_scope or {}),
                "boundary_key": decision.boundary_key,
            },
            description=decision.reason,
            created_at=now,
            status="pending",
        )
        self._durable_services.approval_store.create_request(approval)
        self._run_state_store.update(
            context.task_id,
            context.run_id,
            updated_at=now,
            current_phase="awaiting_approval",
            latest_summary=approval.description,
            awaiting_approval=True,
            pending_approval_id=approval.approval_id,
            is_resumable=True,
            pause_reason="awaiting approval",
        )
        self._publish(
            task_id=context.task_id,
            run_id=context.run_id,
            correlation_id=correlation_id,
            event_type=EventType.APPROVAL_REQUESTED.value,
            timestamp=now,
            source=EventSource(kind=EventSourceKind.POLICY, component="policy-engine"),
            payload={"approval": approval.to_dict()},
        )
        self._increment_approval_metrics(context.task_id, context.run_id)
        return approval

    def _new_checkpoint_thread(self, task_id: str, run_id: str) -> str | None:
        if self._checkpoint_adapter is None:
            return None
        return self._checkpoint_adapter.begin_run(task_id, run_id).thread_id

    def _seed_run_message_history(
        self,
        *,
        task_id: str,
        run_id: str,
        objective: str,
        constraints: list[str],
        success_criteria: list[str],
    ) -> None:
        self._append_run_message(
            task_id=task_id,
            run_id=run_id,
            role="user",
            content=_initial_user_message(
                objective=objective,
                constraints=constraints,
                success_criteria=success_criteria,
            ),
        )

    def _append_run_message(
        self,
        *,
        task_id: str,
        run_id: str,
        role: str,
        content: str,
        created_at: str | None = None,
    ) -> None:
        if self._durable_services is None:
            return
        normalized_content = content.strip()
        if not normalized_content:
            return
        self._durable_services.run_message_store.append_message(
            RunMessageRecord(
                message_id=f"msg_{uuid4().hex}",
                task_id=task_id,
                run_id=run_id,
                role=role,
                content=normalized_content,
                created_at=created_at or utc_now_timestamp(),
            )
        )

    def _load_conversation_messages(self, task_id: str, run_id: str) -> list[dict[str, str]]:
        if self._durable_services is None:
            state = self._run_state_store.get(task_id, run_id)
            return [
                {
                    "role": "user",
                    "content": _initial_user_message(
                        objective=state.objective,
                        constraints=state.constraints,
                        success_criteria=state.success_criteria,
                    ),
                }
            ]
        if self._conversation_compaction_service is not None:
            projected = self._conversation_compaction_service.projected_messages(task_id, run_id)
            if projected:
                return projected
        messages = self._durable_services.run_message_store.list_messages(task_id, run_id)
        if messages:
            return [{"role": message.role, "content": message.content} for message in messages]
        state = self._run_state_store.get(task_id, run_id)
        return [
            {
                "role": "user",
                "content": _initial_user_message(
                    objective=state.objective,
                    constraints=state.constraints,
                    success_criteria=state.success_criteria,
                ),
            }
        ]

    def _allows_explicit_compaction(self, state: RunState) -> bool:
        if (
            not self._compaction_policy.enabled
            or not self._compaction_policy.explicit_client
            or self._conversation_compaction_service is None
        ):
            return False
        if state.status == TaskStatus.ACCEPTED:
            return True
        if state.status in {TaskStatus.PAUSED, TaskStatus.AWAITING_APPROVAL}:
            return True
        return bool(state.is_resumable)

    def _persist_compaction_projection(
        self,
        *,
        task_id: str,
        run_id: str,
        trigger: CompactionTrigger,
    ) -> Any | None:
        if self._conversation_compaction_service is None:
            return None
        record = self._conversation_compaction_service.compact(
            task_id=task_id,
            run_id=run_id,
            trigger=trigger,
        )
        if record is None:
            return None
        now = utc_now_timestamp()
        self._run_state_store.update(
            task_id,
            run_id,
            updated_at=now,
            last_event_at=now,
            latest_summary="Conversation context compacted.",
            is_compacted=True,
            latest_compaction_id=record.compaction_id,
            latest_compaction_trigger=record.trigger,
        )
        return record

    def _install_skill_via_tool(
        self,
        *,
        correlation_id: str | None,
        task_id: str,
        run_id: str,
        sandbox: ExecutionSandbox,
        source_path: str,
        target_scope: str,
        target_role: str | None,
        install_mode: str,
        reason: str,
    ) -> SkillInstallOutcome:
        installer = self._require_skill_installer()
        try:
            prepared = self._prepare_skill_install(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                sandbox=sandbox,
                source_path=source_path,
                target_scope=target_scope,
                target_role=target_role,
                install_mode=install_mode,
                reason=reason,
            )
        except (RecoverableToolRejection, ValueError) as exc:
            return self._failed_skill_install_outcome(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                summary=str(exc),
            )
        if prepared.validation.status == "fail":
            return self._failed_skill_install_outcome(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                summary="Skill installation validation failed.",
                validation=prepared.validation,
                target_path=str(prepared.target_skill_path),
                sandbox=sandbox,
                prepared=prepared,
            )
        self._govern_operation(
            correlation_id=correlation_id,
            context=self._skill_install_operation_context(task_id, run_id, prepared),
        )
        installer.execute_install(prepared)
        artifacts = self._write_skill_install_artifacts(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            sandbox=sandbox,
            prepared=prepared,
        )
        self._publish_skill_install_event(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.SKILL_INSTALL_COMPLETED.value,
            payload={
                "summary": f"Installed skill into {prepared.target_skill_path}.",
                "target_path": str(prepared.target_skill_path),
                "validation": prepared.validation.to_dict(),
            },
        )
        return SkillInstallOutcome(
            status="completed",
            summary=f"Installed skill into {prepared.target_skill_path}.",
            target_path=str(prepared.target_skill_path),
            validation=prepared.validation,
            artifacts=artifacts,
        )

    def _install_skill_via_runtime_method(
        self,
        *,
        correlation_id: str | None,
        task_id: str,
        run_id: str,
        sandbox: ExecutionSandbox,
        source_path: str,
        target_scope: str,
        target_role: str | None,
        install_mode: str,
        reason: str,
    ) -> SkillInstallOutcome:
        installer = self._require_skill_installer()
        try:
            prepared = self._prepare_skill_install(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                sandbox=sandbox,
                source_path=source_path,
                target_scope=target_scope,
                target_role=target_role,
                install_mode=install_mode,
                reason=reason,
            )
        except (RecoverableToolRejection, ValueError) as exc:
            return self._failed_skill_install_outcome(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                summary=str(exc),
            )
        artifacts = self._write_skill_install_artifacts(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            sandbox=sandbox,
            prepared=prepared,
        )
        if prepared.validation.status == "fail":
            return self._failed_skill_install_outcome(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                summary="Skill installation validation failed.",
                validation=prepared.validation,
                target_path=str(prepared.target_skill_path),
                artifacts=artifacts,
            )
        decision = (
            self._durable_services.policy_engine.evaluate(
                self._skill_install_operation_context(task_id, run_id, prepared)
            )
            if self._durable_services is not None
            else PolicyDecision(decision="ALLOW", reason="No durable policy engine configured.")
        )
        if decision.decision == "DENY":
            return self._failed_skill_install_outcome(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                summary=decision.reason,
                validation=prepared.validation,
                target_path=str(prepared.target_skill_path),
                artifacts=artifacts,
                diagnostic_kind="skill_install_denied",
            )
        if decision.decision == "REQUIRE_APPROVAL":
            approval = self._create_skill_install_approval_request(
                correlation_id=correlation_id,
                task_id=task_id,
                run_id=run_id,
                prepared=prepared,
                decision=decision,
            )
            return SkillInstallOutcome(
                status="approval_required",
                summary=approval.description,
                target_path=str(prepared.target_skill_path),
                validation=prepared.validation,
                approval_required=True,
                approval_id=approval.approval_id,
                artifacts=artifacts,
            )
        installer.execute_install(prepared)
        self._publish_skill_install_event(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.SKILL_INSTALL_COMPLETED.value,
            payload={
                "summary": f"Installed skill into {prepared.target_skill_path}.",
                "target_path": str(prepared.target_skill_path),
                "validation": prepared.validation.to_dict(),
            },
        )
        return SkillInstallOutcome(
            status="completed",
            summary=f"Installed skill into {prepared.target_skill_path}.",
            target_path=str(prepared.target_skill_path),
            validation=prepared.validation,
            artifacts=artifacts,
        )

    def _prepare_skill_install(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        sandbox: ExecutionSandbox,
        source_path: str,
        target_scope: str,
        target_role: str | None,
        install_mode: str,
        reason: str,
    ):
        installer = self._require_skill_installer()
        self._publish_skill_install_event(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.SKILL_INSTALL_REQUESTED.value,
            payload={
                "source_path": source_path,
                "target_scope": target_scope,
                "target_role": target_role,
                "install_mode": install_mode,
                "reason": reason,
            },
        )
        prepared = installer.prepare_install(
            sandbox=sandbox,
            source_path=source_path,
            target_scope=target_scope,
            target_role=target_role,
            install_mode=install_mode,
            reason=reason,
        )
        self._publish_skill_install_event(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.SKILL_INSTALL_VALIDATED.value,
            payload={
                "target_path": str(prepared.target_skill_path),
                "validation": prepared.validation.to_dict(),
            },
        )
        return prepared

    def _failed_skill_install_outcome(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        summary: str,
        validation: SkillValidationResult | None = None,
        target_path: str = "",
        artifacts: tuple[str, ...] = (),
        sandbox: ExecutionSandbox | None = None,
        prepared=None,
        diagnostic_kind: str = "skill_install_validation_failed",
    ) -> SkillInstallOutcome:
        resolved_validation = validation or SkillValidationResult(
            status="fail",
            findings=(
                SkillValidationFinding(
                    severity="error",
                    code="invalid_request",
                    message=summary,
                    path=None,
                ),
            ),
            has_scripts=False,
            total_bytes=0,
            file_count=0,
            skill_id=None,
        )
        resolved_artifacts = artifacts
        if sandbox is not None and prepared is not None:
            resolved_artifacts = self._write_skill_install_artifacts(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                sandbox=sandbox,
                prepared=prepared,
            )
        self._append_diagnostic(
            task_id=task_id,
            run_id=run_id,
            kind=diagnostic_kind,
            message=summary,
            details=resolved_validation.to_dict(),
        )
        self._publish_skill_install_event(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.SKILL_INSTALL_FAILED.value,
            payload={
                "summary": summary,
                "target_path": target_path,
                "validation": resolved_validation.to_dict(),
            },
        )
        return SkillInstallOutcome(
            status="failed",
            summary=summary,
            target_path=target_path,
            validation=resolved_validation,
            artifacts=resolved_artifacts,
        )

    def _skill_install_operation_context(
        self, task_id: str, run_id: str, prepared
    ) -> OperationContext:
        return OperationContext(
            task_id=task_id,
            run_id=run_id,
            operation_type="skill.install",
            path_scope=str(prepared.target_skill_path),
            metadata={
                "target_scope": prepared.target.target_scope,
                "target_role": prepared.target.role_id,
                "install_mode": prepared.install_mode,
                "has_scripts": prepared.validation.has_scripts,
                "overwrite": prepared.overwrite,
                "skill_id": prepared.validation.skill_id,
                "source_path": prepared.source_sandbox_path,
            },
        )

    def _ensure_artifacts_loaded(self, task_id: str, run_id: str) -> None:
        if self._durable_services is None:
            return
        key = (task_id, run_id)
        if key in self._rehydrated_artifact_runs:
            return
        state = self._run_state_store.get(task_id, run_id)
        self._sandbox_factory.for_run(
            task_id=task_id,
            run_id=run_id,
            workspace_roots=state.workspace_roots,
        )
        for event in self._durable_services.event_store.get_events(task_id, run_id):
            if event.event_type != EventType.ARTIFACT_CREATED.value:
                continue
            artifact_payload = event.payload.get("artifact")
            if not isinstance(artifact_payload, dict):
                continue
            logical_path = artifact_payload.get("logical_path")
            artifact_id = artifact_payload.get("artifact_id")
            if not isinstance(logical_path, str) or not logical_path.strip():
                continue
            if not isinstance(artifact_id, str) or not artifact_id.strip():
                continue
            try:
                self._artifact_store.restore_artifact(
                    ArtifactReference(
                        artifact_id=artifact_id,
                        task_id=str(artifact_payload.get("task_id") or task_id),
                        run_id=str(artifact_payload.get("run_id") or run_id),
                        logical_path=logical_path,
                        content_type=str(
                            artifact_payload.get("content_type") or "application/octet-stream"
                        ),
                        created_at=str(artifact_payload.get("created_at") or event.timestamp),
                        persistence_class=str(artifact_payload.get("persistence_class") or "run"),
                        source_role=_str_or_none(artifact_payload.get("source_role")),
                        source_tool=_str_or_none(artifact_payload.get("source_tool")),
                        byte_size=_int_or_none(artifact_payload.get("byte_size")),
                        display_name=_str_or_none(artifact_payload.get("display_name")),
                        summary=_str_or_none(artifact_payload.get("summary")),
                        downloadable=(
                            bool(artifact_payload.get("downloadable"))
                            if artifact_payload.get("downloadable") is not None
                            else None
                        ),
                        hash=_str_or_none(artifact_payload.get("hash")),
                    ),
                    sandbox_path=logical_path,
                )
            except (KeyError, ValueError, FileNotFoundError):
                continue
        self._rehydrated_artifact_runs.add(key)

    def _write_skill_install_artifacts(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        sandbox: ExecutionSandbox,
        prepared,
    ) -> tuple[str, ...]:
        installer = self._require_skill_installer()
        artifact_paths: list[str] = []
        existing_paths = {
            artifact.logical_path
            for artifact in self._artifact_store.list_artifacts(task_id, run_id)
        }
        for sandbox_path, content in installer.artifact_payloads(prepared).items():
            if not content:
                continue
            sandbox.write_text(sandbox_path, content)
            artifact = self._artifact_store.register_artifact(
                task_id=task_id,
                run_id=run_id,
                sandbox_path=sandbox_path,
                source_tool="skill_installer",
            )
            artifact_paths.append(sandbox_path)
            state = self._run_state_store.get(task_id, run_id)
            artifact_count = state.artifact_count + (
                0 if artifact.logical_path in existing_paths else 1
            )
            existing_paths.add(artifact.logical_path)
            registered_at = utc_now_timestamp()
            self._run_state_store.update(
                task_id,
                run_id,
                updated_at=registered_at,
                artifact_count=artifact_count,
                last_event_at=registered_at,
            )
            self._publish(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                event_type=EventType.ARTIFACT_CREATED.value,
                timestamp=registered_at,
                source=EventSource(kind=EventSourceKind.RUNTIME, component="artifact-store"),
                payload={"artifact": artifact.to_dict()},
            )
            self._write_metrics(task_id, run_id, artifact_count=artifact_count)
        return tuple(artifact_paths)

    def _require_skill_installer(self) -> SkillInstallationService:
        installer = self._skill_installer
        if installer is None:
            raise ValueError("skill.install requires runtime skill catalog support")
        return installer

    def _publish_skill_install_event(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=event_type,
            timestamp=utc_now_timestamp(),
            source=EventSource(kind=EventSourceKind.RUNTIME, component="skill-installer"),
            payload=payload,
        )

    def _create_skill_install_approval_request(
        self,
        *,
        correlation_id: str | None,
        task_id: str,
        run_id: str,
        prepared,
        decision: PolicyDecision,
    ) -> ApprovalRequest:
        assert self._durable_services is not None
        now = utc_now_timestamp()
        approval = ApprovalRequest(
            approval_id=f"approval_{uuid4().hex[:12]}",
            task_id=task_id,
            run_id=run_id,
            type="skill_install",
            scope={
                "kind": "skill.install",
                "boundary_key": decision.boundary_key,
                "source_path": prepared.source_sandbox_path,
                "target_scope": prepared.target.target_scope,
                "target_role": prepared.target.role_id,
                "install_mode": prepared.install_mode,
                "reason": prepared.reason,
            },
            description=decision.reason,
            created_at=now,
            status="pending",
        )
        self._durable_services.approval_store.create_request(approval)
        self._publish_skill_install_event(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.SKILL_INSTALL_APPROVAL_REQUESTED.value,
            payload={"approval": approval.to_dict()},
        )
        self._publish(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=EventType.APPROVAL_REQUESTED.value,
            timestamp=now,
            source=EventSource(kind=EventSourceKind.POLICY, component="policy-engine"),
            payload={"approval": approval.to_dict()},
        )
        self._increment_approval_metrics(task_id, run_id)
        return approval

    def _approve_skill_install(self, approval: ApprovalRequest, correlation_id: str | None) -> None:
        scope = approval.scope
        boundary_key = scope.get("boundary_key")
        if isinstance(boundary_key, str) and boundary_key and self._durable_services is not None:
            self._durable_services.boundary_grant_store.grant(
                BoundaryGrant(
                    task_id=approval.task_id,
                    run_id=approval.run_id,
                    boundary_key=boundary_key,
                    approval_id=approval.approval_id,
                    granted_at=utc_now_timestamp(),
                )
            )
        outcome = self.skill_install(
            correlation_id=correlation_id,
            task_id=approval.task_id,
            run_id=approval.run_id,
            source_path=str(scope.get("source_path", "")),
            target_scope=str(scope.get("target_scope", "")),
            target_role=scope.get("target_role")
            if isinstance(scope.get("target_role"), str)
            else None,
            install_mode=str(scope.get("install_mode", "")),
            reason=str(scope.get("reason", approval.description)),
        )
        if outcome.status != "completed":
            raise ValueError(outcome.summary)

    def _checkpoint_controller_for_run(
        self,
        task_id: str,
        run_id: str,
        resume: bool,
    ) -> CheckpointController | None:
        if self._checkpoint_adapter is None:
            return None
        if resume:
            return self._checkpoint_adapter.resume_run(task_id, run_id)
        state = self._run_state_store.get(task_id, run_id)
        if state.checkpoint_thread_id is not None:
            return self._checkpoint_adapter.attach_thread(
                task_id,
                run_id,
                state.checkpoint_thread_id,
            )
        return self._checkpoint_adapter.begin_run(task_id, run_id)

    def _increment_checkpoint_metrics(self, task_id: str, run_id: str) -> None:
        self._write_metrics(task_id, run_id, checkpoint_count_increment=1)

    def _increment_resume_metrics(self, task_id: str, run_id: str) -> None:
        self._write_metrics(task_id, run_id, resume_count_increment=1)

    def _increment_approval_metrics(self, task_id: str, run_id: str) -> None:
        self._write_metrics(task_id, run_id, approval_count_increment=1)

    def _write_metrics(
        self,
        task_id: str,
        run_id: str,
        *,
        started_at: str | None = None,
        ended_at: str | None = None,
        artifact_count: int | None = None,
        event_count_increment: int = 0,
        checkpoint_count_increment: int = 0,
        approval_count_increment: int = 0,
        resume_count_increment: int = 0,
        deny_count_increment: int = 0,
    ) -> None:
        if self._durable_services is None:
            return
        record = self._durable_services.run_metrics_store.read_metrics(task_id, run_id)
        if record is None:
            record = _run_metrics_record(task_id, run_id)
        if record.started_at is None and started_at is not None:
            record.started_at = started_at
        if ended_at is not None:
            record.ended_at = ended_at
        if artifact_count is not None:
            record.artifact_count = artifact_count
        record.event_count += event_count_increment
        record.checkpoint_count += checkpoint_count_increment
        record.approval_count += approval_count_increment
        record.resume_count += resume_count_increment
        record.deny_count += deny_count_increment
        record.last_updated_at = utc_now_timestamp()
        self._durable_services.run_metrics_store.write_metrics(record)


def _source_for_harness_event(event_type: str, payload: dict[str, Any]) -> EventSource:
    if event_type in {
        EventType.SUBAGENT_STARTED.value,
        EventType.SUBAGENT_COMPLETED.value,
    }:
        role = str(payload.get("subagentId", "subagent"))
        return EventSource(
            kind=EventSourceKind.SUBAGENT,
            role=role,
            name=role,
            component="langchain-deepagent-harness",
        )
    if event_type in {EventType.TOOL_CALLED.value, EventType.TOOL_REJECTED.value}:
        return EventSource(
            kind=EventSourceKind.TOOL,
            name=str(payload.get("tool", "sandbox-tool")),
            component="sandbox-tool-bindings",
        )
    if event_type == EventType.MEMORY_UPDATED.value:
        return EventSource(
            kind=EventSourceKind.MEMORY,
            name=str(payload.get("memory_id", "memory-record")),
            component="sandbox-tool-bindings",
        )
    return EventSource(kind=EventSourceKind.RUNTIME, component="langchain-deepagent-harness")


def _todos_from_event_payload(payload: dict[str, Any]) -> list[TodoItem] | None:
    if str(payload.get("tool", "")).strip() != "write_todos":
        return None
    arguments = payload.get("arguments")
    if not isinstance(arguments, dict) or "todos" not in arguments:
        return []
    return normalize_todos(arguments.get("todos"))


def _run_metrics_record(
    task_id: str,
    run_id: str,
) -> RunMetricsRecord:
    return RunMetricsRecord(
        task_id=task_id,
        run_id=run_id,
        last_updated_at=utc_now_timestamp(),
    )


def _initial_user_message(
    *,
    objective: str,
    constraints: list[str],
    success_criteria: list[str],
) -> str:
    sections = [
        objective.strip(),
        "",
        "Complete the objective using governed tools and native Deep Agent delegation when it improves focus or isolation.",
    ]
    if constraints:
        sections.extend(["", "Constraints:"])
        sections.extend(f"- {item}" for item in constraints if item.strip())
    if success_criteria:
        sections.extend(["", "Success Criteria:"])
        sections.extend(f"- {item}" for item in success_criteria if item.strip())
    return "\n".join(sections).strip()


def _str_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None
