from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


MCPAuthorizationMode = Literal["static_headers", "oauth_user_grant"]


@dataclass(frozen=True, slots=True)
class MCPAuthorizationConfig:
    mode: MCPAuthorizationMode = "static_headers"
    provider: str | None = None


@dataclass(frozen=True, slots=True)
class OAuthProviderConfig:
    provider_id: str
    authorization_url: str | None = None
    token_url: str | None = None
    discovery_url: str | None = None
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    scopes: tuple[str, ...] = ()
    audience: str | None = None
    resource: str | None = None


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
    auth: MCPAuthorizationConfig = field(default_factory=MCPAuthorizationConfig)
    source: str = "runtime_toml"
    source_path: str | None = None


@dataclass(frozen=True, slots=True)
class MCPConfig:
    tool_name_prefix: bool = True
    servers: dict[str, MCPServerConfig] = field(default_factory=dict)
    oauth_providers: dict[str, OAuthProviderConfig] = field(default_factory=dict)


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


@dataclass(frozen=True, slots=True)
class CompactionSize:
    kind: str
    value: float | int


@dataclass(slots=True)
class CompactionConfig:
    enabled: bool = True
    strategy: str = "deepagents_native"
    automatic: bool = True
    explicit_client: bool = True
    explicit_agent_tool: bool = True
    trigger: CompactionSize = field(default_factory=lambda: CompactionSize("fraction", 0.85))
    keep: CompactionSize = field(default_factory=lambda: CompactionSize("fraction", 0.10))
    fallback_trigger: CompactionSize = field(
        default_factory=lambda: CompactionSize("tokens", 170000)
    )
    tool_token_limit_before_evict: int = 20000


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
    compaction: CompactionConfig = field(default_factory=CompactionConfig)
