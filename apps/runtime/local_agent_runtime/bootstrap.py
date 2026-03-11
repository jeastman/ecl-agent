from __future__ import annotations

from apps.runtime.local_agent_runtime.artifact_store import InMemoryArtifactStore
from apps.runtime.local_agent_runtime.durable_services import create_durable_runtime_services
from apps.runtime.local_agent_runtime.event_bus import InMemoryEventBus
from apps.runtime.local_agent_runtime.method_handlers import MethodHandlers
from apps.runtime.local_agent_runtime.memory_seed import seed_identity_memory
from apps.runtime.local_agent_runtime.recovery_service import RecoveryService
from apps.runtime.local_agent_runtime.resume_service import ResumeService
from apps.runtime.local_agent_runtime.run_state_store import InMemoryRunStateStore
from apps.runtime.local_agent_runtime.runtime_server import RuntimeServer
from apps.runtime.local_agent_runtime.task_runner import AgentHarness, TaskRunner

from packages.config.local_agent_config.models import RuntimeConfig
from packages.identity.local_agent_identity.models import IdentityBundle
from services.deepagent_runtime.local_agent_deepagent_runtime.deepagent_harness import (
    LangChainDeepAgentHarness,
)
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    LocalExecutionSandboxFactory,
)


def create_runtime_server(
    config: RuntimeConfig,
    identity: IdentityBundle,
    *,
    agent_harness: AgentHarness | None = None,
    runtime_root: str | None = None,
    config_path: str | None = None,
) -> RuntimeServer:
    run_state_store = InMemoryRunStateStore()
    event_bus = InMemoryEventBus()
    durable_services = create_durable_runtime_services(
        config,
        runtime_root_override=runtime_root,
    )
    seed_identity_memory(identity, durable_services.memory_store)
    resolved_runtime_root = durable_services.root_path
    sandbox_factory = LocalExecutionSandboxFactory(runtime_root=resolved_runtime_root)
    artifact_store = InMemoryArtifactStore(path_mapper=sandbox_factory)
    task_runner = TaskRunner(
        run_state_store=run_state_store,
        event_bus=event_bus,
        artifact_store=artifact_store,
        sandbox_factory=sandbox_factory,
        durable_services=durable_services,
        agent_harness=agent_harness
        or LangChainDeepAgentHarness(
            model_name=config.default_model.model,
            model_provider=config.default_model.provider,
        ),
    )
    checkpoint_adapter = task_runner.checkpoint_adapter
    assert checkpoint_adapter is not None
    recovery_service = RecoveryService(
        run_state_store=run_state_store,
        event_store=durable_services.event_store,
        checkpoint_adapter=checkpoint_adapter,
    )
    recovery_service.recover()
    resume_service = ResumeService(
        task_runner=task_runner,
        identity_bundle_text=identity.content,
    )
    handlers = MethodHandlers(
        config=config,
        identity=identity,
        run_state_store=run_state_store,
        event_bus=event_bus,
        artifact_store=artifact_store,
        task_runner=task_runner,
        durable_services=durable_services,
        resume_service=resume_service,
        config_sources=[source for source in (config_path, config.identity_path) if source is not None],
    )
    return RuntimeServer(handlers=handlers)
