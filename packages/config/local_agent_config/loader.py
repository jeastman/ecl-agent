from __future__ import annotations

import json
import tomllib
from pathlib import Path, PurePosixPath

from packages.config.local_agent_config.models import (
    CliConfig,
    MCPConfig,
    MCPServerConfig,
    ModelConfig,
    PersistenceConfig,
    RuntimeConfig,
    RuntimeSettings,
    TransportConfig,
)


def _required_table(payload: dict, key: str) -> dict:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"missing required table: {key}")
    return value


def _required_str(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required string: {key}")
    return value.strip()


def _resolve_path(base_path: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_path / candidate).resolve()


def _resolve_backend(
    payload: dict,
    key: str,
    *,
    default: str,
    allowed: set[str],
) -> str:
    value = payload.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    resolved = value.strip()
    if resolved not in allowed:
        raise ValueError(f"{key} must be one of: {', '.join(sorted(allowed))}")
    return resolved


def _resolve_virtual_workspace_root(payload: dict) -> str:
    raw = payload.get("virtual_workspace_root", "/workspace")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("virtual_workspace_root must be a non-empty string")
    candidate = PurePosixPath(raw.strip())
    if not candidate.is_absolute():
        raise ValueError("virtual_workspace_root must be an absolute virtual path")
    for part in candidate.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError("virtual_workspace_root cannot traverse outside its virtual root")
    return candidate.as_posix()


def _optional_bool(payload: dict[str, object], key: str, *, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _optional_string_map(payload: object, key: str) -> dict[str, str]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"{key} must be a table/object")
    resolved: dict[str, str] = {}
    for item_key, item_value in payload.items():
        if not isinstance(item_key, str) or not item_key.strip():
            raise ValueError(f"{key} keys must be non-empty strings")
        if not isinstance(item_value, str):
            raise ValueError(f"{key}.{item_key} must be a string")
        resolved[item_key] = item_value
    return resolved


def _optional_string_list(payload: object, key: str) -> tuple[str, ...]:
    if payload is None:
        return ()
    if not isinstance(payload, list):
        raise ValueError(f"{key} must be a list")
    resolved: list[str] = []
    for item in payload:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{key} must contain non-empty strings")
        resolved.append(item)
    return tuple(resolved)


def _normalize_mcp_transport(raw_transport: str | None) -> str | None:
    if raw_transport is None:
        return None
    normalized = raw_transport.strip().lower().replace("-", "_")
    if not normalized:
        return None
    if normalized in {"stdio", "sse", "http", "streamable_http"}:
        return normalized
    raise ValueError(
        "MCP transport must be one of: stdio, sse, http, streamable_http, streamable-http"
    )


def _parse_mcp_server_config(
    *,
    name: str,
    payload: dict[str, object],
    source: str,
    source_path: str,
) -> MCPServerConfig:
    enabled = _optional_bool(payload, "enabled", default=True)
    description_value = payload.get("description")
    if description_value is not None and not isinstance(description_value, str):
        raise ValueError(f"MCP server {name} description must be a string when present")
    description = None if description_value in (None, "") else str(description_value)

    command = payload.get("command")
    url = payload.get("url")
    command_value = None
    url_value = None
    if command is not None:
        if not isinstance(command, str) or not command.strip():
            raise ValueError(f"MCP server {name} command must be a non-empty string")
        command_value = command.strip()
    if url is not None:
        if not isinstance(url, str) or not url.strip():
            raise ValueError(f"MCP server {name} url must be a non-empty string")
        url_value = url.strip()

    raw_transport = payload.get("transport", payload.get("type"))
    if raw_transport is not None and not isinstance(raw_transport, str):
        raise ValueError(f"MCP server {name} transport must be a string when present")
    transport = _normalize_mcp_transport(raw_transport)

    if command_value is not None and url_value is not None:
        raise ValueError(f"MCP server {name} cannot define both command and url")
    if command_value is None and url_value is None:
        raise ValueError(f"MCP server {name} must define either command or url")

    if command_value is not None:
        if transport is None:
            transport = "stdio"
        if transport != "stdio":
            raise ValueError(f"MCP server {name} command-based entries must use stdio transport")
        return MCPServerConfig(
            name=name,
            transport=transport,
            enabled=enabled,
            description=description,
            command=command_value,
            args=_optional_string_list(payload.get("args"), f"mcp.servers.{name}.args"),
            env=_optional_string_map(payload.get("env"), f"mcp.servers.{name}.env"),
            source=source,
            source_path=source_path,
        )

    if transport is None:
        raise ValueError(f"MCP server {name} remote entries must define transport or type")
    if transport == "stdio":
        raise ValueError(f"MCP server {name} url-based entries cannot use stdio transport")

    return MCPServerConfig(
        name=name,
        transport=transport,
        enabled=enabled,
        description=description,
        url=url_value,
        headers=_optional_string_map(payload.get("headers"), f"mcp.servers.{name}.headers"),
        source=source,
        source_path=source_path,
    )


def _parse_mcp_servers_table(
    payload: object,
    *,
    source: str,
    source_path: str,
) -> dict[str, MCPServerConfig]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("mcp.servers must be a table/object")
    servers: dict[str, MCPServerConfig] = {}
    for name, server_payload in payload.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("mcp server names must be non-empty strings")
        if not isinstance(server_payload, dict):
            raise ValueError(f"MCP server {name} must be a table/object")
        servers[name] = _parse_mcp_server_config(
            name=name.strip(),
            payload=server_payload,
            source=source,
            source_path=source_path,
        )
    return servers


def _discover_project_root(config_dir: Path) -> Path:
    current = config_dir.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _load_mcp_json_file(path: Path, *, source: str) -> dict[str, MCPServerConfig]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in MCP config: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"MCP config must be a JSON object: {path}")
    return _parse_mcp_servers_table(
        payload.get("mcpServers"),
        source=source,
        source_path=str(path.resolve()),
    )


def _resolve_mcp_config(config_path: Path, mcp_payload: dict[str, object]) -> MCPConfig:
    if not isinstance(mcp_payload, dict):
        raise ValueError("mcp must be a table")
    project_root = _discover_project_root(config_path.parent)
    servers: dict[str, MCPServerConfig] = {}
    servers.update(
        _load_mcp_json_file(
            project_root / ".deepagents" / ".mcp.json",
            source="project_deepagents_mcp_json",
        )
    )
    servers.update(
        _load_mcp_json_file(
            project_root / ".mcp.json",
            source="project_root_mcp_json",
        )
    )
    servers.update(
        _parse_mcp_servers_table(
            mcp_payload.get("servers"),
            source="runtime_toml",
            source_path=str(config_path.resolve()),
        )
    )
    return MCPConfig(
        tool_name_prefix=_optional_bool(mcp_payload, "tool_name_prefix", default=True),
        servers=servers,
    )


def load_runtime_config(path: str) -> RuntimeConfig:
    config_path = Path(path)
    if not config_path.is_file():
        raise ValueError(f"config file not found: {path}")

    with config_path.open("rb") as handle:
        payload = tomllib.load(handle)

    runtime_payload = _required_table(payload, "runtime")
    transport_payload = _required_table(payload, "transport")
    identity_payload = _required_table(payload, "identity")
    model_payload = _required_table(payload, "models")
    default_model_payload = model_payload.get("default")
    primary_model_payload = _required_table(model_payload, "primary")
    persistence_payload = payload.get("persistence", {})
    cli_payload = payload.get("cli", {})
    policy_payload = payload.get("policy", {})
    mcp_payload = payload.get("mcp", {})
    if not isinstance(persistence_payload, dict):
        raise ValueError("persistence must be a table")
    if not isinstance(cli_payload, dict):
        raise ValueError("cli must be a table")
    if not isinstance(policy_payload, dict):
        raise ValueError("policy must be a table")
    if not isinstance(mcp_payload, dict):
        raise ValueError("mcp must be a table")

    subagent_overrides_payload = model_payload.get("subagents", {})
    if not isinstance(subagent_overrides_payload, dict):
        raise ValueError("models.subagents must be a table")
    if default_model_payload is not None and not isinstance(default_model_payload, dict):
        raise ValueError("models.default must be a table")

    resolved_identity_path = _resolve_path(
        config_path.parent, _required_str(identity_payload, "path")
    )
    default_root = (Path.home() / ".local-agent-harness").resolve()
    raw_root = persistence_payload.get("root_path", str(default_root))
    if not isinstance(raw_root, str) or not raw_root.strip():
        raise ValueError("root_path must be a non-empty string")
    resolved_root_path = _resolve_path(config_path.parent, raw_root.strip())
    metadata_backend = _resolve_backend(
        persistence_payload,
        "metadata_backend",
        default="sqlite",
        allowed={"sqlite"},
    )

    return RuntimeConfig(
        runtime=RuntimeSettings(
            name=_required_str(runtime_payload, "name"),
            log_level=str(runtime_payload.get("log_level", "info")),
        ),
        identity_path=str(resolved_identity_path),
        transport=TransportConfig(mode=_required_str(transport_payload, "mode")),
        primary_model=ModelConfig(
            provider=_required_str(primary_model_payload, "provider"),
            model=_required_str(primary_model_payload, "model"),
        ),
        default_model=(
            None
            if default_model_payload is None
            else ModelConfig(
                provider=_required_str(default_model_payload, "provider"),
                model=_required_str(default_model_payload, "model"),
            )
        ),
        persistence=PersistenceConfig(
            root_path=str(resolved_root_path),
            metadata_backend=metadata_backend,
            event_backend=_resolve_backend(
                persistence_payload,
                "event_backend",
                default=metadata_backend,
                allowed={"sqlite"},
            ),
            diagnostic_backend=_resolve_backend(
                persistence_payload,
                "diagnostic_backend",
                default=metadata_backend,
                allowed={"sqlite"},
            ),
        ),
        cli=CliConfig(
            default_workspace_root=(
                None
                if cli_payload.get("default_workspace_root") in (None, "")
                else str(
                    _resolve_path(
                        config_path.parent,
                        _required_str(cli_payload, "default_workspace_root"),
                    )
                )
            ),
            virtual_workspace_root=_resolve_virtual_workspace_root(cli_payload),
        ),
        subagent_model_overrides={
            role: ModelConfig(
                provider=_required_str(value, "provider"),
                model=_required_str(value, "model"),
            )
            for role, value in subagent_overrides_payload.items()
            if isinstance(value, dict)
        },
        policy=policy_payload,
        mcp=_resolve_mcp_config(config_path, mcp_payload),
    )
