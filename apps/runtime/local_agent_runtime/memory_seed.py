from __future__ import annotations

from packages.identity.local_agent_identity.models import IdentityBundle
from packages.protocol.local_agent_protocol.models import utc_now_timestamp
from services.memory_service.local_agent_memory_service.memory_models import MemoryRecord
from services.memory_service.local_agent_memory_service.memory_promotion import (
    MEMORY_SCOPE_IDENTITY,
)
from services.memory_service.local_agent_memory_service.memory_store import MemoryStore


def seed_identity_memory(identity: IdentityBundle, memory_store: MemoryStore) -> None:
    timestamp = utc_now_timestamp()
    summary_line = identity.content.strip().splitlines()[0] if identity.content.strip() else ""
    memory_store.write_memory(
        MemoryRecord(
            memory_id=f"identity:{identity.sha256}",
            scope=MEMORY_SCOPE_IDENTITY,
            namespace="identity.bundle",
            content=identity.content,
            summary=summary_line or "Runtime identity bundle",
            provenance={
                "source_path": identity.source_path,
                "version": identity.version,
                "sha256": identity.sha256,
                "kind": "identity_bundle",
            },
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
