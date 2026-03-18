from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MCPServerConfig:
    name: str
    transport: str
    enabled: bool = True
    description: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    env_from_host: tuple[str, ...] = ()
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    source: str = "runtime_toml"
    source_path: str | None = None


@dataclass(frozen=True, slots=True)
class MCPConfig:
    tool_name_prefix: bool = True
    servers: dict[str, MCPServerConfig] = field(default_factory=dict)


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
class CliConfig:
    default_workspace_root: str | None = None
    virtual_workspace_root: str = "/workspace"


@dataclass(slots=True)
class RuntimeConfig:
    runtime: RuntimeSettings
    identity_path: str
    transport: TransportConfig
    primary_model: ModelConfig
    persistence: PersistenceConfig
    cli: CliConfig = field(default_factory=CliConfig)
    default_model: ModelConfig | None = None
    subagent_model_overrides: dict[str, ModelConfig] = field(default_factory=dict)
    policy: dict[str, object] = field(default_factory=dict)
    mcp: MCPConfig = field(default_factory=MCPConfig)
