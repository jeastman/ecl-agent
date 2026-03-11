from __future__ import annotations

from apps.runtime.local_agent_runtime.artifact_store import InMemoryArtifactStore
from apps.runtime.local_agent_runtime.event_bus import InMemoryEventBus
from apps.runtime.local_agent_runtime.method_handlers import MethodHandlers
from apps.runtime.local_agent_runtime.run_state_store import InMemoryRunStateStore
from apps.runtime.local_agent_runtime.runtime_server import RuntimeServer
from apps.runtime.local_agent_runtime.task_runner import StubAgentHarness, TaskRunner
from packages.config.local_agent_config.models import RuntimeConfig
from packages.identity.local_agent_identity.models import IdentityBundle


def create_runtime_server(config: RuntimeConfig, identity: IdentityBundle) -> RuntimeServer:
    run_state_store = InMemoryRunStateStore()
    event_bus = InMemoryEventBus()
    artifact_store = InMemoryArtifactStore()
    task_runner = TaskRunner(
        run_state_store=run_state_store,
        event_bus=event_bus,
        artifact_store=artifact_store,
        agent_harness=StubAgentHarness(),
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
