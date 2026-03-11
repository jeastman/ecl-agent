from __future__ import annotations

import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

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
        self.assertEqual(payload["result"]["protocol_version"], "1.0.0")

    def test_invalid_config_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "invalid.toml"
            config_path.write_text("[runtime]\nname = 'broken'\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing required table"):
                load_runtime_config(str(config_path))

    def test_missing_identity_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "identity file not found"):
            load_identity_bundle("/tmp/does-not-exist-identity.md")

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
        self.assertIn("protocol=1.0.0", completed.stdout)

        stderr_lines = [line for line in completed.stderr.strip().splitlines() if line.strip()]
        event_records = [json.loads(line) for line in stderr_lines if '"type": "runtime.event"' in line]
        self.assertEqual(len(event_records), 2)
        self.assertEqual(event_records[0]["event"]["event_type"], "task.created")
        self.assertEqual(event_records[1]["event"]["event_type"], "task.accepted")
        self.assertTrue(event_records[0]["event"]["correlation_id"].startswith("corr_"))
        self.assertEqual(event_records[0]["protocol_version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
