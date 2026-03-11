from __future__ import annotations

import tomllib
from pathlib import Path

from packages.config.local_agent_config.models import (
    ModelConfig,
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
    default_model_payload = _required_table(model_payload, "default")
    policy_payload = payload.get("policy", {})
    if not isinstance(policy_payload, dict):
        raise ValueError("policy must be a table")

    subagent_overrides_payload = model_payload.get("subagents", {})
    if not isinstance(subagent_overrides_payload, dict):
        raise ValueError("models.subagents must be a table")

    resolved_identity_path = (
        config_path.parent / _required_str(identity_payload, "path")
    ).resolve()

    return RuntimeConfig(
        runtime=RuntimeSettings(
            name=_required_str(runtime_payload, "name"),
            log_level=str(runtime_payload.get("log_level", "info")),
        ),
        identity_path=str(resolved_identity_path),
        transport=TransportConfig(mode=_required_str(transport_payload, "mode")),
        default_model=ModelConfig(
            provider=_required_str(default_model_payload, "provider"),
            model=_required_str(default_model_payload, "model"),
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
