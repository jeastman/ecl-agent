from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from packages.protocol.local_agent_protocol.models import ArtifactReference
from services.artifact_service.local_agent_artifact_service.store import InMemoryArtifactStore
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    LocalExecutionSandboxFactory,
)


class ArtifactStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self._temp_dir.cleanup)
        self.workspace_root = Path(self._temp_dir.name) / "workspace"
        self.workspace_root.mkdir()
        self.factory = LocalExecutionSandboxFactory(
            runtime_root=Path(self._temp_dir.name) / "runtime",
            governed_workspace_root=self.workspace_root,
        )
        self.sandbox = self.factory.for_run(
            task_id="task_1",
            run_id="run_1",
            workspace_roots=["/workspace"],
        )
        self.store = InMemoryArtifactStore(path_mapper=self.factory)

    def test_register_artifact_maps_sandbox_path_to_logical_path(self) -> None:
        self.sandbox.write_text("/tmp/repo_summary.md", "# Summary\n")
        artifact = self.store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="/tmp/repo_summary.md",
        )
        self.assertEqual(artifact.logical_path, "/tmp/repo_summary.md")
        self.assertEqual(artifact.content_type, "text/markdown")
        self.assertEqual(artifact.persistence_class, "ephemeral")
        self.assertEqual(artifact.display_name, "repo_summary.md")
        self.assertIsNotNone(artifact.hash)

    def test_workspace_artifacts_are_exposed_relative_to_workspace_root(self) -> None:
        self.sandbox.write_text("/workspace/artifacts/repo_summary.md", "# Summary\n")
        artifact = self.store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="/workspace/artifacts/repo_summary.md",
        )
        self.assertEqual(artifact.logical_path, "/workspace/artifacts/repo_summary.md")
        self.assertEqual(artifact.persistence_class, "run")

    def test_lookup_supports_task_run_and_filters(self) -> None:
        self.sandbox.write_text("/tmp/repo_summary.md", "# Summary\n")
        self.sandbox.write_text("/.memory/session.json", "{}\n")
        self.store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="/tmp/repo_summary.md",
        )
        self.store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="/.memory/session.json",
        )
        self.assertEqual(len(self.store.list_artifacts("task_1", "run_1")), 2)
        self.assertEqual(len(self.store.list_artifacts("task_1", persistence_class="project")), 1)
        self.assertEqual(
            len(self.store.list_artifacts("task_1", content_type_prefix="text/")),
            1,
        )

    def test_duplicate_registration_updates_existing_logical_path(self) -> None:
        self.sandbox.write_text("/tmp/repo_summary.md", "# Summary\n")
        first = self.store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="/tmp/repo_summary.md",
        )
        self.sandbox.write_text("/tmp/repo_summary.md", "# Updated Summary\n")
        second = self.store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="/tmp/repo_summary.md",
        )
        artifacts = self.store.list_artifacts("task_1", "run_1")
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(first.artifact_id, second.artifact_id)
        self.assertEqual(artifacts[0].byte_size, len("# Updated Summary\n"))

    def test_restore_artifact_rehydrates_existing_metadata(self) -> None:
        self.sandbox.write_text("/workspace/artifacts/final_response.md", "# Final\n")
        restored = self.store.restore_artifact(
            ArtifactReference(
                artifact_id="artifact_1",
                task_id="task_1",
                run_id="run_1",
                logical_path="/workspace/artifacts/final_response.md",
                content_type="text/markdown",
                created_at="2026-03-12T00:00:00Z",
                persistence_class="run",
                display_name="final_response.md",
                hash="existing-hash",
            ),
            sandbox_path="/workspace/artifacts/final_response.md",
        )
        self.assertEqual(restored.artifact_id, "artifact_1")
        self.assertEqual(restored.logical_path, "/workspace/artifacts/final_response.md")
        self.assertEqual(
            self.store.get_artifact("task_1", "artifact_1", "run_1").artifact_id, "artifact_1"
        )


if __name__ == "__main__":
    unittest.main()
