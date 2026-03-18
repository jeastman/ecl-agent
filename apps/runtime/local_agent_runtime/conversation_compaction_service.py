from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.task_model.local_agent_task_model.models import CompactionTrigger
from services.deepagent_runtime.local_agent_deepagent_runtime.compaction_strategy import (
    CompactionStrategyPort,
)
from services.observability_service.local_agent_observability_service.conversation_compaction_store import (
    ConversationCompactionStore,
)
from services.observability_service.local_agent_observability_service.message_store import RunMessageStore
from services.observability_service.local_agent_observability_service.observability_models import (
    ConversationCompactionRecord,
)


@dataclass(slots=True)
class ConversationCompactionService:
    run_message_store: RunMessageStore
    compaction_store: ConversationCompactionStore
    strategy: CompactionStrategyPort

    def projected_messages(self, task_id: str, run_id: str) -> list[dict[str, str]]:
        canonical = self._canonical_messages(task_id, run_id)
        latest = self.compaction_store.latest_compaction(task_id, run_id)
        if latest is None:
            return canonical
        tail = canonical[latest.cutoff_index :]
        return [
            {"role": "user", "content": latest.summary_content},
            *tail,
        ]

    def latest_snapshot(self, task_id: str, run_id: str) -> ConversationCompactionRecord | None:
        return self.compaction_store.latest_compaction(task_id, run_id)

    def compact(
        self,
        *,
        task_id: str,
        run_id: str,
        trigger: CompactionTrigger,
    ) -> ConversationCompactionRecord | None:
        canonical = self._canonical_messages(task_id, run_id)
        result = self.strategy.compact_messages(messages=canonical, trigger=trigger)
        if result.snapshot is None:
            return None
        record = ConversationCompactionRecord(
            compaction_id=result.snapshot.compaction_id,
            task_id=task_id,
            run_id=run_id,
            trigger=result.snapshot.trigger.value,
            strategy=result.snapshot.strategy,
            cutoff_index=result.snapshot.cutoff_index,
            summary_content=result.snapshot.summary_content,
            created_at=result.snapshot.created_at,
            provenance=dict(result.snapshot.provenance),
            artifact_path=result.snapshot.artifact_path,
        )
        self.compaction_store.append_compaction(record)
        return record

    def _canonical_messages(self, task_id: str, run_id: str) -> list[dict[str, str]]:
        return [
            {"role": message.role, "content": message.content}
            for message in self.run_message_store.list_messages(task_id, run_id)
        ]
