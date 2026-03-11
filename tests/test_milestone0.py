from __future__ import annotations

import json
import subprocess
import sys
import unittest

from packages.config.local_agent_config.loader import load_runtime_config
from packages.identity.local_agent_identity.loader import load_identity_bundle
from packages.protocol.local_agent_protocol.models import JsonRpcRequest
from packages.task_model.local_agent_task_model.ids import new_correlation_id


CONFIG_PATH = "docs/architecture/runtime.example.toml"


class Milestone0Tests(unittest.TestCase):
    def test_config_and_identity_load(self) -> None:
        config = load_runtime_config(CONFIG_PATH)
        identity = load_identity_bundle(config.identity_path)

        self.assertEqual(config.transport.mode, "stdio-jsonrpc")
        self.assertTrue(identity.version.startswith("sha256:"))

    def test_runtime_health_round_trip(self) -> None:
        request = JsonRpcRequest(
            method="runtime.health",
            params={},
            id="1",
            correlation_id=new_correlation_id(),
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "apps.runtime.local_agent_runtime.main",
                "--config",
                CONFIG_PATH,
            ],
            input=json.dumps(request.to_dict()) + "\n",
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout.strip())
        self.assertEqual(payload["result"]["status"], "ok")
        self.assertEqual(payload["correlation_id"], request.correlation_id)

    def test_cli_submit_round_trip(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "apps.cli.local_agent_cli.cli",
                "--config",
                CONFIG_PATH,
                "submit",
                "Bootstrap Milestone 0",
                "--constraint",
                "stay within repo",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("task_id=task_", completed.stdout)
        self.assertIn("status=accepted", completed.stdout)


if __name__ == "__main__":
    unittest.main()
