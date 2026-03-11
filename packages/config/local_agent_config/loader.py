from __future__ import annotations

import tomllib
from pathlib import Path

from packages.config.local_agent_config.models import (
    CliConfig,
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
    if not isinstance(persistence_payload, dict):
        raise ValueError("persistence must be a table")
    if not isinstance(cli_payload, dict):
        raise ValueError("cli must be a table")
    if not isinstance(policy_payload, dict):
        raise ValueError("policy must be a table")

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
            )
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
    )
