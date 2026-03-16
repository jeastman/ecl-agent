from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir

from packages.config.local_agent_config.models import RuntimeConfig
from services.checkpoint_service.local_agent_checkpoint_service.checkpoint_store import (
    CheckpointStore,
    SQLiteCheckpointStore,
)
from services.checkpoint_service.local_agent_checkpoint_service.thread_registry import (
    SQLiteThreadRegistry,
    ThreadRegistry,
)
from services.memory_service.local_agent_memory_service.memory_store import (
    MemoryStore,
    SQLiteMemoryStore,
)
from services.memory_service.local_agent_memory_service.memory_promotion import (
    MemoryPromotionService,
)
from services.observability_service.local_agent_observability_service.diagnostic_store import (
    DiagnosticStore,
    SQLiteDiagnosticStore,
)
from services.observability_service.local_agent_observability_service.event_store import (
    EventStore,
    SQLiteEventStore,
)
from services.observability_service.local_agent_observability_service.message_store import (
    RunMessageStore,
    SQLiteRunMessageStore,
)
from services.observability_service.local_agent_observability_service.run_metrics_store import (
    RunMetricsStore,
    SQLiteRunMetricsStore,
)
from services.policy_service.local_agent_policy_service.approval_store import (
    ApprovalStore,
    SQLiteApprovalStore,
)
from services.policy_service.local_agent_policy_service.boundary_scope import (
    BoundaryGrantStore,
    SQLiteBoundaryGrantStore,
)
from services.policy_service.local_agent_policy_service.policy_engine import (
    PolicyEngine,
    RuntimePolicyEngine,
)


@dataclass(slots=True)
class DurableRuntimeServices:
    root_path: str
    database_path: str
    checkpoint_store: CheckpointStore
    thread_registry: ThreadRegistry
    memory_store: MemoryStore
    memory_promotion_service: MemoryPromotionService
    approval_store: ApprovalStore
    boundary_grant_store: BoundaryGrantStore
    policy_engine: PolicyEngine
    event_store: EventStore
    diagnostic_store: DiagnosticStore
    run_metrics_store: RunMetricsStore
    run_message_store: RunMessageStore


def create_durable_runtime_services(
    config: RuntimeConfig,
    *,
    runtime_root_override: str | None = None,
) -> DurableRuntimeServices:
    root_path = _resolve_runtime_root(runtime_root_override or config.persistence.root_path)
    metadata_root = root_path / "metadata"
    metadata_root.mkdir(parents=True, exist_ok=True)
    database_path = metadata_root / "runtime.db"
    database_path.touch(exist_ok=True)

    thread_registry = SQLiteThreadRegistry(str(database_path))
    boundary_grant_store = SQLiteBoundaryGrantStore(str(database_path))
    return DurableRuntimeServices(
        root_path=str(root_path),
        database_path=str(database_path),
        checkpoint_store=SQLiteCheckpointStore(str(database_path), thread_registry=thread_registry),
        thread_registry=thread_registry,
        memory_store=SQLiteMemoryStore(str(database_path)),
        memory_promotion_service=MemoryPromotionService(),
        approval_store=SQLiteApprovalStore(str(database_path)),
        boundary_grant_store=boundary_grant_store,
        policy_engine=RuntimePolicyEngine(
            policy_config=config.policy,
            boundary_grants=boundary_grant_store,
        ),
        event_store=SQLiteEventStore(str(database_path)),
        diagnostic_store=SQLiteDiagnosticStore(str(database_path)),
        run_metrics_store=SQLiteRunMetricsStore(str(database_path)),
        run_message_store=SQLiteRunMessageStore(str(database_path)),
    )


def _resolve_runtime_root(configured_root: str) -> Path:
    candidate = Path(configured_root).expanduser()
    fallback = Path(gettempdir()) / "local-agent-harness"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        metadata_root = candidate / "metadata"
        metadata_root.mkdir(parents=True, exist_ok=True)
        probe = metadata_root / ".write-probe"
        probe.touch(exist_ok=True)
        probe.unlink(missing_ok=True)
        return candidate.resolve()
    except PermissionError:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback.resolve()
