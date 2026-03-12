from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OpenArtifactAction:
    artifact_id: str
    task_id: str
    run_id: str
    destination: str
    external_open_supported: bool


def build_open_artifact_action(
    *,
    artifact_id: str,
    task_id: str,
    run_id: str,
    content_type: str,
    external_open_supported: bool,
) -> OpenArtifactAction:
    destination = "markdown_viewer" if content_type == "text/markdown" else "external"
    return OpenArtifactAction(
        artifact_id=artifact_id,
        task_id=task_id,
        run_id=run_id,
        destination=destination,
        external_open_supported=external_open_supported,
    )
