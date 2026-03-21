from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AuthorizedMCPGrant:
    provider_id: str
    runtime_user_id: str
    access_token: str
    refresh_token: str | None
    token_type: str
    scopes: tuple[str, ...]
    expires_at: str | None
    account_key: str = "default"
    status: str = "authorized"


@dataclass(frozen=True, slots=True)
class PendingOAuthAuthorization:
    authorization_id: str
    server_name: str
    provider_id: str
    runtime_user_id: str
    state_token: str
    authorization_url: str
    created_at: str
    run_id: str | None = None
    task_id: str | None = None


@dataclass(frozen=True, slots=True)
class RemoteMCPActionDescriptor:
    action_id: str
    method: str
    title: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RemoteMCPAuthorizationState:
    server_name: str
    provider_id: str
    status: str
    summary: str
    actions: tuple[RemoteMCPActionDescriptor, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["actions"] = [action.to_dict() for action in self.actions]
        return payload
