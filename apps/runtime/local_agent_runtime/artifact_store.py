from __future__ import annotations

from typing import Protocol

from packages.protocol.local_agent_protocol.models import ArtifactReference


class ArtifactStore(Protocol):
    def list_artifacts(self, task_id: str, run_id: str | None = None) -> list[ArtifactReference]:
        ...


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self._artifacts: dict[tuple[str, str], list[ArtifactReference]] = {}

    def list_artifacts(self, task_id: str, run_id: str | None = None) -> list[ArtifactReference]:
        if run_id is None:
            artifacts: list[ArtifactReference] = []
            for (candidate_task_id, _), records in self._artifacts.items():
                if candidate_task_id == task_id:
                    artifacts.extend(records)
            return artifacts
        return list(self._artifacts.get((task_id, run_id), []))
