from __future__ import annotations

from apps.runtime.local_agent_runtime.artifact_store import InMemoryArtifactStore
from apps.runtime.local_agent_runtime.event_bus import InMemoryEventBus
from apps.runtime.local_agent_runtime.method_handlers import MethodHandlers
from apps.runtime.local_agent_runtime.run_state_store import InMemoryRunStateStore
from apps.runtime.local_agent_runtime.runtime_server import RuntimeServer
from apps.runtime.local_agent_runtime.task_runner import AgentHarness, StubAgentHarness, TaskRunner
from pathlib import Path
import tempfile

from packages.config.local_agent_config.models import RuntimeConfig
from packages.identity.local_agent_identity.models import IdentityBundle
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    LocalExecutionSandboxFactory,
)


def create_runtime_server(
    config: RuntimeConfig,
    identity: IdentityBundle,
    *,
    agent_harness: AgentHarness | None = None,
    runtime_root: str | None = None,
) -> RuntimeServer:
    run_state_store = InMemoryRunStateStore()
    event_bus = InMemoryEventBus()
    resolved_runtime_root = runtime_root or str(Path(tempfile.gettempdir()) / "local-agent-harness")
    sandbox_factory = LocalExecutionSandboxFactory(runtime_root=resolved_runtime_root)
    artifact_store = InMemoryArtifactStore(path_mapper=sandbox_factory)
    task_runner = TaskRunner(
        run_state_store=run_state_store,
        event_bus=event_bus,
        artifact_store=artifact_store,
        sandbox_factory=sandbox_factory,
        agent_harness=agent_harness or StubAgentHarness(),
    )
    handlers = MethodHandlers(
        config=config,
        identity=identity,
        run_state_store=run_state_store,
        event_bus=event_bus,
        artifact_store=artifact_store,
        task_runner=task_runner,
    )
    return RuntimeServer(handlers=handlers)
