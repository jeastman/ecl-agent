from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.runtime.local_agent_runtime.bootstrap import create_runtime_server
from apps.runtime.local_agent_runtime.task_runner import StubAgentHarness
from packages.config.local_agent_config.loader import load_runtime_config
from packages.identity.local_agent_identity.loader import load_identity_bundle
from services.sandbox_service.local_agent_sandbox_service.sandbox import (
    LocalExecutionSandboxFactory,
)


class BootstrapTests(unittest.TestCase):
    def test_runtime_bootstrap_composes_durable_services(self) -> None:
        config = load_runtime_config("docs/architecture/runtime.example.toml")
        identity = load_identity_bundle(config.identity_path)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            runtime_root = Path(temp_dir) / "runtime"
            server = create_runtime_server(
                config=config,
                identity=identity,
                agent_harness=StubAgentHarness(),
                runtime_root=str(runtime_root),
            )

            services = server.handlers.durable_services

            self.assertEqual(services.root_path, str(runtime_root.resolve()))
            self.assertTrue(Path(services.database_path).is_file())
            self.assertEqual(
                services.policy_engine.evaluate(context=_operation_context()).decision,
                "ALLOW",
            )
            identity_records = services.memory_store.list_memory(scope="identity")
            self.assertEqual(len(identity_records), 1)
            self.assertEqual(identity_records[0].namespace, "identity.bundle")
            resolved_subagents = server.handlers.task_runner.resolved_subagents
            self.assertEqual(
                [resolved.asset_bundle.definition.role_id for resolved in resolved_subagents],
                ["coder", "librarian", "planner", "researcher", "verifier"],
            )
            researcher = next(
                resolved
                for resolved in resolved_subagents
                if resolved.asset_bundle.definition.role_id == "researcher"
            )
            self.assertEqual(researcher.model_route.source, "subagent_override")
            self.assertEqual(researcher.model_route.model, "gpt-5-mini")
            default_model = config.default_model
            self.assertIsNotNone(default_model)
            assert default_model is not None
            self.assertEqual(default_model.model, "gpt-5-nano")
            self.assertEqual(
                [binding.tool_id for binding in researcher.tool_bindings],
                ["read_files", "memory_lookup"],
            )
            self.assertEqual(researcher.skills, ())
            self.assertIn(
                "runtime-governance",
                [skill.skill_id for skill in server.handlers.task_runner.primary_skills],
            )

    def test_runtime_bootstrap_uses_configured_workspace_root_for_sandbox_governance(self) -> None:
        config = load_runtime_config("docs/architecture/runtime.example.toml")
        identity = load_identity_bundle(config.identity_path)
        config.cli.default_workspace_root = "/tmp/configured-workspace"
        captured: dict[str, object] = {}
        original_init = LocalExecutionSandboxFactory.__init__

        def recording_init(
            self,
            runtime_root: str | Path,
            governed_workspace_root: str | Path,
        ) -> None:
            captured["runtime_root"] = Path(runtime_root)
            captured["governed_workspace_root"] = Path(governed_workspace_root)
            original_init(self, runtime_root, governed_workspace_root)

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            runtime_root = Path(temp_dir) / "runtime"
            with patch.object(LocalExecutionSandboxFactory, "__init__", new=recording_init):
                create_runtime_server(
                    config=config,
                    identity=identity,
                    agent_harness=StubAgentHarness(),
                    runtime_root=str(runtime_root),
                )

        self.assertEqual(captured["runtime_root"], runtime_root.resolve())
        self.assertEqual(
            captured["governed_workspace_root"],
            Path("/tmp/configured-workspace").resolve(),
        )

    def test_runtime_bootstrap_falls_back_to_cwd_for_sandbox_governance(self) -> None:
        config = load_runtime_config("docs/architecture/runtime.example.toml")
        identity = load_identity_bundle(config.identity_path)
        config.cli.default_workspace_root = None
        captured: dict[str, object] = {}
        original_init = LocalExecutionSandboxFactory.__init__

        def recording_init(
            self,
            runtime_root: str | Path,
            governed_workspace_root: str | Path,
        ) -> None:
            captured["governed_workspace_root"] = Path(governed_workspace_root)
            original_init(self, runtime_root, governed_workspace_root)

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            runtime_root = Path(temp_dir) / "runtime"
            with patch.object(LocalExecutionSandboxFactory, "__init__", new=recording_init):
                create_runtime_server(
                    config=config,
                    identity=identity,
                    agent_harness=StubAgentHarness(),
                    runtime_root=str(runtime_root),
                )

        self.assertEqual(captured["governed_workspace_root"], Path.cwd().resolve())


def _operation_context():
    from services.policy_service.local_agent_policy_service.policy_models import OperationContext

    return OperationContext(
        task_id="task_1",
        run_id="run_1",
        operation_type="write_file",
    )


if __name__ == "__main__":
    unittest.main()
