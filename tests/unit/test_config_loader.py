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

    def test_loader_parses_native_mcp_server_config(self) -> None:
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
                        "[mcp]",
                        "tool_name_prefix = true",
                        "",
                        "[mcp.servers.fixture]",
                        "command = 'python3'",
                        "args = ['tests/fixtures/mcp_echo_server.py']",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_runtime_config(str(config_path))

            self.assertTrue(config.mcp.tool_name_prefix)
            server = config.mcp.servers["fixture"]
            self.assertEqual(server.transport, "stdio")
            self.assertEqual(server.command, "python3")
            self.assertEqual(server.args, ("tests/fixtures/mcp_echo_server.py",))
            self.assertEqual(server.source, "runtime_toml")

    def test_loader_imports_project_mcp_json_with_runtime_precedence(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            project_root = Path(temp_dir)
            (project_root / ".git").mkdir()
            (project_root / ".deepagents").mkdir()
            (project_root / ".deepagents" / ".mcp.json").write_text(
                """
                {
                  "mcpServers": {
                    "deepagents-fixture": {
                      "command": "python3",
                      "args": ["tests/fixtures/mcp_echo_server.py"]
                    },
                    "shared": {
                      "type": "http",
                      "url": "https://deepagents.example.com/mcp"
                    }
                  }
                }
                """.strip(),
                encoding="utf-8",
            )
            (project_root / ".mcp.json").write_text(
                """
                {
                  "mcpServers": {
                    "root-fixture": {
                      "command": "python3",
                      "args": ["tests/fixtures/mcp_echo_server.py"]
                    },
                    "shared": {
                      "type": "http",
                      "url": "https://root.example.com/mcp"
                    }
                  }
                }
                """.strip(),
                encoding="utf-8",
            )
            config_path = project_root / "runtime.toml"
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
                        "[mcp.servers.shared]",
                        "transport = 'http'",
                        "url = 'https://runtime.example.com/mcp'",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_runtime_config(str(config_path))

            self.assertIn("deepagents-fixture", config.mcp.servers)
            self.assertIn("root-fixture", config.mcp.servers)
            self.assertEqual(config.mcp.servers["shared"].url, "https://runtime.example.com/mcp")
            self.assertEqual(config.mcp.servers["shared"].source, "runtime_toml")

    def test_loader_rejects_invalid_mcp_server_shapes(self) -> None:
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
                        "[mcp.servers.broken]",
                        "command = 'python3'",
                        "url = 'https://example.com/mcp'",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "cannot define both command and url"):
                load_runtime_config(str(config_path))


if __name__ == "__main__":
    unittest.main()
