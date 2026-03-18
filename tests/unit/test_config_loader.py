from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from packages.config.local_agent_config.loader import load_runtime_config


class RuntimeConfigLoaderTests(unittest.TestCase):
    def test_loader_applies_default_persistence_settings(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            config_path = Path(temp_dir) / "runtime.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[runtime]",
                        "name = 'local-agent-harness'",
                        "",
                        "[transport]",
                        "mode = 'stdio-jsonrpc'",
                        "",
                        "[identity]",
                        "path = '../agents/primary-agent/IDENTITY.md'",
                        "",
                        "[models.primary]",
                        "provider = 'openai'",
                        "model = 'gpt-5'",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_runtime_config(str(config_path))

            self.assertIsNone(config.default_model)
            self.assertEqual(config.persistence.metadata_backend, "sqlite")
            self.assertEqual(config.persistence.event_backend, "sqlite")
            self.assertEqual(config.persistence.diagnostic_backend, "sqlite")
            self.assertTrue(config.persistence.root_path.endswith(".local-agent-harness"))

    def test_loader_parses_optional_default_model(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            config_path = Path(temp_dir) / "runtime.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[runtime]",
                        "name = 'local-agent-harness'",
                        "",
                        "[transport]",
                        "mode = 'stdio-jsonrpc'",
                        "",
                        "[identity]",
                        "path = '../agents/primary-agent/IDENTITY.md'",
                        "",
                        "[models.default]",
                        "provider = 'openai'",
                        "model = 'gpt-5-mini'",
                        "",
                        "[models.primary]",
                        "provider = 'openai'",
                        "model = 'gpt-5'",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_runtime_config(str(config_path))

            assert config.default_model is not None
            self.assertEqual(config.default_model.provider, "openai")
            self.assertEqual(config.default_model.model, "gpt-5-mini")

    def test_loader_resolves_explicit_relative_persistence_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "runtime.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[runtime]",
                        "name = 'local-agent-harness'",
                        "",
                        "[transport]",
                        "mode = 'stdio-jsonrpc'",
                        "",
                        "[identity]",
                        "path = '../../agents/primary-agent/IDENTITY.md'",
                        "",
                        "[models.primary]",
                        "provider = 'openai'",
                        "model = 'gpt-5'",
                        "",
                        "[persistence]",
                        "root_path = '../state'",
                        "metadata_backend = 'sqlite'",
                        "event_backend = 'sqlite'",
                        "diagnostic_backend = 'sqlite'",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_runtime_config(str(config_path))

            self.assertEqual(config.persistence.root_path, str((config_dir / "../state").resolve()))

    def test_loader_resolves_cli_default_workspace_root_relative_to_config(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "runtime.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[runtime]",
                        "name = 'local-agent-harness'",
                        "",
                        "[transport]",
                        "mode = 'stdio-jsonrpc'",
                        "",
                        "[identity]",
                        "path = '../../agents/primary-agent/IDENTITY.md'",
                        "",
                        "[models.primary]",
                        "provider = 'openai'",
                        "model = 'gpt-5'",
                        "",
                        "[cli]",
                        "default_workspace_root = '../workspace'",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_runtime_config(str(config_path))

            self.assertEqual(
                config.cli.default_workspace_root,
                str((config_dir / "../workspace").resolve()),
            )
            self.assertEqual(config.cli.virtual_workspace_root, "/workspace")

    def test_loader_resolves_explicit_virtual_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            config_path = Path(temp_dir) / "runtime.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[runtime]",
                        "name = 'local-agent-harness'",
                        "",
                        "[transport]",
                        "mode = 'stdio-jsonrpc'",
                        "",
                        "[identity]",
                        "path = '../agents/primary-agent/IDENTITY.md'",
                        "",
                        "[models.primary]",
                        "provider = 'openai'",
                        "model = 'gpt-5'",
                        "",
                        "[cli]",
                        "virtual_workspace_root = '/workspace/project'",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_runtime_config(str(config_path))

            self.assertEqual(config.cli.virtual_workspace_root, "/workspace/project")

    def test_loader_rejects_unknown_persistence_backend(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            config_path = Path(temp_dir) / "runtime.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[runtime]",
                        "name = 'local-agent-harness'",
                        "",
                        "[transport]",
                        "mode = 'stdio-jsonrpc'",
                        "",
                        "[identity]",
                        "path = '../agents/primary-agent/IDENTITY.md'",
                        "",
                        "[models.primary]",
                        "provider = 'openai'",
                        "model = 'gpt-5'",
                        "",
                        "[persistence]",
                        "metadata_backend = 'json'",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "metadata_backend must be one of"):
                load_runtime_config(str(config_path))


if __name__ == "__main__":
    unittest.main()
