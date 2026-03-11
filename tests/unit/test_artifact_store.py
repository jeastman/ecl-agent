from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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
            runtime_root=Path(self._temp_dir.name) / "runtime"
        )
        self.sandbox = self.factory.for_run(
            task_id="task_1",
            run_id="run_1",
            workspace_roots=[str(self.workspace_root)],
        )
        self.store = InMemoryArtifactStore(path_mapper=self.factory)

    def test_register_artifact_maps_sandbox_path_to_logical_path(self) -> None:
        self.sandbox.write_text("scratch/repo_summary.md", "# Summary\n")
        artifact = self.store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="scratch/repo_summary.md",
        )
        self.assertEqual(artifact.logical_path, "scratch/repo_summary.md")
        self.assertEqual(artifact.content_type, "text/markdown")
        self.assertEqual(artifact.persistence_class, "ephemeral")
        self.assertEqual(artifact.display_name, "repo_summary.md")
        self.assertIsNotNone(artifact.hash)

    def test_lookup_supports_task_run_and_filters(self) -> None:
        self.sandbox.write_text("scratch/repo_summary.md", "# Summary\n")
        self.sandbox.write_text("memory/session.json", "{}\n")
        self.store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="scratch/repo_summary.md",
        )
        self.store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="memory/session.json",
        )
        self.assertEqual(len(self.store.list_artifacts("task_1", "run_1")), 2)
        self.assertEqual(len(self.store.list_artifacts("task_1", persistence_class="project")), 1)
        self.assertEqual(
            len(self.store.list_artifacts("task_1", content_type_prefix="text/")),
            1,
        )

    def test_duplicate_registration_updates_existing_logical_path(self) -> None:
        self.sandbox.write_text("scratch/repo_summary.md", "# Summary\n")
        first = self.store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="scratch/repo_summary.md",
        )
        self.sandbox.write_text("scratch/repo_summary.md", "# Updated Summary\n")
        second = self.store.register_artifact(
            task_id="task_1",
            run_id="run_1",
            sandbox_path="scratch/repo_summary.md",
        )
        artifacts = self.store.list_artifacts("task_1", "run_1")
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(first.artifact_id, second.artifact_id)
        self.assertEqual(artifacts[0].byte_size, len("# Updated Summary\n"))


if __name__ == "__main__":
    unittest.main()
