from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.sandbox_service.local_agent_sandbox_service.path_policy import (
    ensure_within_root,
    normalize_sandbox_path,
)
from services.sandbox_service.local_agent_sandbox_service.workspace_manager import WorkspaceManager


class SandboxPathPolicyTests(unittest.TestCase):
    def test_normalize_valid_paths(self) -> None:
        self.assertEqual(
            normalize_sandbox_path("/workspace/src/app.py").logical_path,
            "/workspace/src/app.py",
        )
        self.assertEqual(normalize_sandbox_path("/tmp").logical_path, "/tmp")
        self.assertEqual(
            normalize_sandbox_path("/.memory/notes.md").logical_path, "/.memory/notes.md"
        )

    def test_reject_out_of_bounds_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute virtual path"):
            normalize_sandbox_path("tmp/escape.txt")
        with self.assertRaisesRegex(ValueError, "cannot traverse"):
            normalize_sandbox_path("/tmp/../escape.txt")
        with self.assertRaisesRegex(ValueError, "cannot traverse"):
            normalize_sandbox_path("/.memory/../../output.md")
        with self.assertRaisesRegex(ValueError, "under /workspace, /tmp, or /.memory"):
            normalize_sandbox_path("/src/app.py")

    def test_zone_roots_resolve_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            runtime_root = workspace_root / "runtime"
            manager = WorkspaceManager(runtime_root, workspace_root)
            roots = manager.create_roots(
                task_id="task_1",
                run_id="run_1",
                workspace_roots=["/workspace"],
            )
            self.assertEqual(roots.workspace_root, workspace_root.resolve())
            self.assertEqual(
                roots.scratch_root, (runtime_root / "scratch" / "task_1" / "run_1").resolve()
            )
            self.assertEqual(roots.memory_root, (runtime_root / "memory" / "task_1").resolve())
            self.assertEqual(roots.virtual_workspace_root.as_posix(), "/workspace")

    def test_workspace_root_accepts_nested_path_within_governing_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            governed_workspace_root = Path(temp_dir) / "workspace"
            governed_workspace_root.mkdir()
            nested_workspace_root = governed_workspace_root / "nested"
            nested_workspace_root.mkdir()
            manager = WorkspaceManager(Path(temp_dir) / "runtime", governed_workspace_root)

            roots = manager.create_roots(
                task_id="task_1",
                run_id="run_1",
                workspace_roots=["/workspace/nested"],
            )

            self.assertEqual(roots.workspace_root, nested_workspace_root.resolve())

    def test_workspace_root_rejects_path_outside_governing_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            governed_workspace_root = Path(temp_dir) / "workspace"
            governed_workspace_root.mkdir()
            outside_workspace_root = Path(temp_dir) / "outside"
            outside_workspace_root.mkdir()
            manager = WorkspaceManager(Path(temp_dir) / "runtime", governed_workspace_root)

            with self.assertRaisesRegex(ValueError, "under /workspace, /tmp, or /.memory"):
                manager.create_roots(
                    task_id="task_1",
                    run_id="run_1",
                    workspace_roots=["/outside"],
                )

    def test_ensure_within_root_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir).resolve()
            outside = root.parent
            with self.assertRaisesRegex(ValueError, "escapes governed sandbox root"):
                ensure_within_root(root, outside)


if __name__ == "__main__":
    unittest.main()
