from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from packages.task_model.local_agent_task_model.models import RecoverableToolRejection
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    LocalExecutionSandboxFactory,
)


class LocalExecutionSandboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self._temp_dir.cleanup)
        self.workspace_root = Path(self._temp_dir.name) / "workspace"
        self.workspace_root.mkdir()
        (self.workspace_root / "README.md").write_text("hello\n", encoding="utf-8")
        self.runtime_root = Path(self._temp_dir.name) / "runtime"
        self.factory = LocalExecutionSandboxFactory(
            runtime_root=self.runtime_root,
            governed_workspace_root=self.workspace_root,
        )
        self.sandbox = self.factory.for_run(
            task_id="task_1",
            run_id="run_1",
            workspace_roots=["/workspace"],
        )

    def test_read_write_only_inside_governed_zones(self) -> None:
        self.sandbox.write_text("/tmp/output.md", "# generated\n")
        self.assertEqual(self.sandbox.read_text("/tmp/output.md"), "# generated\n")
        self.assertEqual(self.sandbox.read_text("/workspace/README.md"), "hello\n")
        with self.assertRaisesRegex(RecoverableToolRejection, "cannot traverse"):
            self.sandbox.write_text("/workspace/../escape.txt", "bad")

    def test_command_execution_allows_governed_cwd(self) -> None:
        result = self.sandbox.execute_command(["pwd"], cwd="/workspace")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Path(result.cwd), self.workspace_root.resolve())

    def test_command_execution_rejects_invalid_working_directory(self) -> None:
        with self.assertRaisesRegex(RecoverableToolRejection, "absolute virtual path"):
            self.sandbox.execute_command(["pwd"], cwd="workspace")

    def test_host_workspace_paths_are_rejected(self) -> None:
        host_path = self.workspace_root / "README.md"
        with self.assertRaisesRegex(RecoverableToolRejection, "host-native path"):
            self.sandbox.normalize_path(str(host_path))
        with self.assertRaisesRegex(RecoverableToolRejection, "host-native path"):
            self.sandbox.read_text(str(host_path))

    def test_virtual_root_getters_do_not_expose_host_paths(self) -> None:
        self.assertEqual(self.sandbox.get_workspace_root(), "/workspace")
        self.assertEqual(self.sandbox.get_scratch_root(), "/tmp")
        self.assertEqual(self.sandbox.get_memory_root(), "/.memory")

    def test_list_files_stays_rooted(self) -> None:
        nested = self.workspace_root / "src"
        nested.mkdir()
        (nested / "main.py").write_text("print('hi')\n", encoding="utf-8")
        files = self.sandbox.list_files("/workspace")
        self.assertIn("/workspace/README.md", files)
        self.assertIn("/workspace/src/main.py", files)


if __name__ == "__main__":
    unittest.main()
