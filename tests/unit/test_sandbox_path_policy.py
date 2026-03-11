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
            normalize_sandbox_path("workspace/src/app.py").logical_path, "workspace/src/app.py"
        )
        self.assertEqual(normalize_sandbox_path("scratch").logical_path, "scratch")
        self.assertEqual(normalize_sandbox_path("memory/notes.md").logical_path, "memory/notes.md")

    def test_reject_out_of_bounds_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "relative to a governed zone"):
            normalize_sandbox_path("/tmp/escape.txt")
        with self.assertRaisesRegex(ValueError, "cannot traverse"):
            normalize_sandbox_path("workspace/../escape.txt")
        with self.assertRaisesRegex(ValueError, "unsupported sandbox zone"):
            normalize_sandbox_path("artifacts/output.md")

    def test_zone_roots_resolve_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            workspace_root = Path(temp_dir)
            runtime_root = workspace_root / "runtime"
            manager = WorkspaceManager(runtime_root)
            roots = manager.create_roots(
                task_id="task_1",
                run_id="run_1",
                workspace_roots=[str(workspace_root)],
            )
            self.assertEqual(roots.workspace_root, workspace_root.resolve())
            self.assertEqual(
                roots.scratch_root, (runtime_root / "scratch" / "task_1" / "run_1").resolve()
            )
            self.assertEqual(roots.memory_root, (runtime_root / "memory" / "task_1").resolve())

    def test_ensure_within_root_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir).resolve()
            outside = root.parent
            with self.assertRaisesRegex(ValueError, "escapes governed sandbox root"):
                ensure_within_root(root, outside)


if __name__ == "__main__":
    unittest.main()
