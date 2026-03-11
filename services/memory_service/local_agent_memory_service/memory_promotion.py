from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from services.memory_service.local_agent_memory_service.memory_models import MemoryRecord

MEMORY_SCOPE_RUN_STATE: Final[str] = "run_state"
MEMORY_SCOPE_PROJECT: Final[str] = "project"
MEMORY_SCOPE_IDENTITY: Final[str] = "identity"
MEMORY_SCOPE_SCRATCH: Final[str] = "scratch"

VALID_MEMORY_SCOPES: Final[frozenset[str]] = frozenset(
    {
        MEMORY_SCOPE_RUN_STATE,
        MEMORY_SCOPE_PROJECT,
        MEMORY_SCOPE_IDENTITY,
        MEMORY_SCOPE_SCRATCH,
    }
)
PROMOTABLE_MEMORY_SCOPES: Final[frozenset[str]] = frozenset(
    {
        MEMORY_SCOPE_RUN_STATE,
        MEMORY_SCOPE_SCRATCH,
    }
)
AGENT_WRITABLE_MEMORY_SCOPES: Final[frozenset[str]] = frozenset(
    {
        MEMORY_SCOPE_RUN_STATE,
        MEMORY_SCOPE_SCRATCH,
    }
)


@dataclass(slots=True)
class MemoryPromotionService:
    def validate_scope(self, scope: str) -> str:
        normalized = scope.strip()
        if normalized not in VALID_MEMORY_SCOPES:
            raise ValueError(f"unknown memory scope: {scope}")
        return normalized

    def can_agent_write(self, scope: str) -> bool:
        return self.validate_scope(scope) in AGENT_WRITABLE_MEMORY_SCOPES

    def promote(
        self,
        record: MemoryRecord,
        *,
        target_scope: str = MEMORY_SCOPE_PROJECT,
        promoted_at: str,
    ) -> MemoryRecord:
        source_scope = self.validate_scope(record.scope)
        normalized_target = self.validate_scope(target_scope)
        if normalized_target != MEMORY_SCOPE_PROJECT:
            raise ValueError("memory promotion target must be project")
        if source_scope not in PROMOTABLE_MEMORY_SCOPES:
            raise ValueError(f"memory in scope {source_scope} is not promotable")

        provenance = dict(record.provenance)
        provenance["promotion"] = {
            "from_scope": source_scope,
            "to_scope": normalized_target,
            "promoted_at": promoted_at,
        }
        return replace(
            record,
            scope=normalized_target,
            provenance=provenance,
            updated_at=promoted_at,
        )
