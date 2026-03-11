from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Protocol

from packages.protocol.local_agent_protocol.models import ArtifactReference, utc_now_timestamp
from packages.task_model.local_agent_task_model.ids import new_artifact_id
from services.sandbox_service.local_agent_sandbox_service.sandbox import SandboxPathMapper


class ArtifactStore(Protocol):
    def register_artifact(
        self,
        *,
        task_id: str,
        run_id: str,
        sandbox_path: str,
        persistence_class: str | None = None,
        source_role: str | None = None,
        source_tool: str | None = None,
        summary: str | None = None,
    ) -> ArtifactReference: ...

    def list_artifacts(
        self,
        task_id: str,
        run_id: str | None = None,
        persistence_class: str | None = None,
        content_type_prefix: str | None = None,
    ) -> list[ArtifactReference]: ...


class InMemoryArtifactStore:
    def __init__(self, path_mapper: SandboxPathMapper) -> None:
        self._path_mapper = path_mapper
        self._artifacts: dict[tuple[str, str], list[ArtifactReference]] = {}

    def register_artifact(
        self,
        *,
        task_id: str,
        run_id: str,
        sandbox_path: str,
        persistence_class: str | None = None,
        source_role: str | None = None,
        source_tool: str | None = None,
        summary: str | None = None,
    ) -> ArtifactReference:
        logical_path, host_path, inferred_persistence_class = (
            self._path_mapper.materialize_artifact_path(
                task_id=task_id,
                run_id=run_id,
                sandbox_path=sandbox_path,
            )
        )
        resolved_persistence_class = persistence_class or inferred_persistence_class
        artifact = ArtifactReference(
            artifact_id=self._existing_artifact_id(task_id, run_id, logical_path)
            or new_artifact_id(),
            task_id=task_id,
            run_id=run_id,
            logical_path=logical_path,
            content_type=_guess_content_type(host_path),
            created_at=utc_now_timestamp(),
            persistence_class=resolved_persistence_class,
            source_role=source_role,
            source_tool=source_tool,
            byte_size=host_path.stat().st_size,
            display_name=host_path.name,
            summary=summary,
            hash=_sha256(host_path),
        )
        records = self._artifacts.setdefault((task_id, run_id), [])
        for index, existing in enumerate(records):
            if existing.logical_path == logical_path:
                records[index] = artifact
                break
        else:
            records.append(artifact)
        return artifact

    def list_artifacts(
        self,
        task_id: str,
        run_id: str | None = None,
        persistence_class: str | None = None,
        content_type_prefix: str | None = None,
    ) -> list[ArtifactReference]:
        records: list[ArtifactReference] = []
        for (candidate_task_id, candidate_run_id), artifacts in self._artifacts.items():
            if candidate_task_id != task_id:
                continue
            if run_id is not None and candidate_run_id != run_id:
                continue
            records.extend(artifacts)
        return [
            artifact
            for artifact in records
            if (persistence_class is None or artifact.persistence_class == persistence_class)
            and (
                content_type_prefix is None or artifact.content_type.startswith(content_type_prefix)
            )
        ]

    def _existing_artifact_id(self, task_id: str, run_id: str, logical_path: str) -> str | None:
        for artifact in self._artifacts.get((task_id, run_id), []):
            if artifact.logical_path == logical_path:
                return artifact.artifact_id
        return None


def _guess_content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
