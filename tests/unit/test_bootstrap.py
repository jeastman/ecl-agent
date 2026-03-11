from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.runtime.local_agent_runtime.bootstrap import create_runtime_server
from apps.runtime.local_agent_runtime.task_runner import StubAgentHarness
from packages.config.local_agent_config.loader import load_runtime_config
from packages.identity.local_agent_identity.loader import load_identity_bundle


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


def _operation_context():
    from services.policy_service.local_agent_policy_service.policy_models import OperationContext

    return OperationContext(
        task_id="task_1",
        run_id="run_1",
        operation_type="write_file",
    )


if __name__ == "__main__":
    unittest.main()
