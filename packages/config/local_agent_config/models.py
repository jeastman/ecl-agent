from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TransportConfig:
    mode: str


@dataclass(slots=True)
class ModelConfig:
    provider: str
    model: str


@dataclass(slots=True)
class RuntimeSettings:
    name: str
    log_level: str = "info"


@dataclass(slots=True)
class PersistenceConfig:
    root_path: str
    metadata_backend: str = "sqlite"
    event_backend: str = "sqlite"
    diagnostic_backend: str = "sqlite"


@dataclass(slots=True)
class RuntimeConfig:
    runtime: RuntimeSettings
    identity_path: str
    transport: TransportConfig
    default_model: ModelConfig
    persistence: PersistenceConfig
    subagent_model_overrides: dict[str, ModelConfig] = field(default_factory=dict)
    policy: dict[str, object] = field(default_factory=dict)
