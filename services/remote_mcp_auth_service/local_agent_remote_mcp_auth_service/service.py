from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from packages.config.local_agent_config.models import MCPConfig, MCPServerConfig, OAuthProviderConfig
from packages.protocol.local_agent_protocol.models import (
    METHOD_REMOTE_MCP_AUTHORIZE_COMPLETE,
    METHOD_REMOTE_MCP_AUTHORIZE_START,
    METHOD_REMOTE_MCP_REAUTHORIZE,
    utc_now_timestamp,
)
from services.policy_service.local_agent_policy_service.policy_models import OperationContext
from services.remote_mcp_auth_service.local_agent_remote_mcp_auth_service.models import (
    AuthorizedMCPGrant,
    PendingOAuthAuthorization,
    RemoteMCPActionDescriptor,
    RemoteMCPAuthorizationState,
)
from services.remote_mcp_auth_service.local_agent_remote_mcp_auth_service.store import (
    RemoteMCPGrantStore,
)


class AuthorizationRequiredError(RuntimeError):
    def __init__(self, state: RemoteMCPAuthorizationState) -> None:
        super().__init__(state.summary)
        self.state = state


class OAuthTokenClient:
    def exchange_code(self, provider: OAuthProviderConfig, code: str) -> dict[str, Any]:
        return self._post_form(
            provider,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": provider.redirect_uri,
                "client_id": provider.client_id,
                "client_secret": provider.client_secret,
            },
        )

    def refresh(self, provider: OAuthProviderConfig, refresh_token: str) -> dict[str, Any]:
        return self._post_form(
            provider,
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": provider.client_id,
                "client_secret": provider.client_secret,
            },
        )

    def _post_form(self, provider: OAuthProviderConfig, form: dict[str, str]) -> dict[str, Any]:
        token_url = _resolve_provider_endpoint(provider, "token")
        request = Request(
            token_url,
            data=urlencode(form).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))


class RemoteMCPAuthService:
    def __init__(
        self,
        *,
        mcp_config: MCPConfig,
        grant_store: RemoteMCPGrantStore,
        token_client: OAuthTokenClient | None = None,
        governed_operation: Callable[[OperationContext], None] | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._mcp_config = mcp_config
        self._grant_store = grant_store
        self._token_client = token_client or OAuthTokenClient()
        self._governed_operation = governed_operation
        self._on_event = on_event

    def start_authorization(
        self,
        *,
        task_id: str | None,
        run_id: str | None,
        server_name: str,
        runtime_user_id: str,
    ) -> PendingOAuthAuthorization:
        server = self._server(server_name)
        provider = self._provider(server)
        authorization_id = f"mcpauth_{uuid4().hex}"
        state_token = base64.urlsafe_b64encode(hashlib.sha256(authorization_id.encode("utf-8")).digest()).decode("ascii").rstrip("=")
        params = {
            "response_type": "code",
            "client_id": provider.client_id,
            "redirect_uri": provider.redirect_uri,
            "state": state_token,
        }
        if provider.scopes:
            params["scope"] = " ".join(provider.scopes)
        if provider.audience is not None:
            params["audience"] = provider.audience
        if provider.resource is not None:
            params["resource"] = provider.resource
        authorization = PendingOAuthAuthorization(
            authorization_id=authorization_id,
            server_name=server_name,
            provider_id=provider.provider_id,
            runtime_user_id=runtime_user_id,
            state_token=state_token,
            authorization_url=f"{_resolve_provider_endpoint(provider, 'authorization')}?{urlencode(params)}",
            created_at=utc_now_timestamp(),
            task_id=task_id,
            run_id=run_id,
        )
        self._grant_store.save_pending_authorization(authorization)
        self._govern("remote_mcp.auth.start", task_id=task_id, run_id=run_id, server_name=server_name, provider_id=provider.provider_id)
        self._emit("remote_mcp.auth.started", {"server_name": server_name, "provider_id": provider.provider_id})
        return authorization

    def complete_authorization(
        self,
        *,
        authorization_id: str,
        state_token: str,
        code: str,
    ) -> AuthorizedMCPGrant:
        pending = self._grant_store.get_pending_authorization(authorization_id)
        if pending is None:
            raise ValueError("unknown remote MCP authorization request")
        if pending.state_token != state_token:
            raise ValueError("remote MCP authorization state token mismatch")
        provider = self._mcp_config.oauth_providers[pending.provider_id]
        self._govern(
            "remote_mcp.auth.complete",
            task_id=pending.task_id,
            run_id=pending.run_id,
            server_name=pending.server_name,
            provider_id=pending.provider_id,
            target=_resolve_provider_endpoint(provider, "token"),
        )
        token_payload = self._token_client.exchange_code(provider, code)
        grant = _grant_from_token_payload(
            provider_id=provider.provider_id,
            runtime_user_id=pending.runtime_user_id,
            token_payload=token_payload,
        )
        self._grant_store.save_grant(grant)
        self._grant_store.delete_pending_authorization(authorization_id)
        self._emit("remote_mcp.auth.completed", {"server_name": pending.server_name, "provider_id": provider.provider_id})
        return grant

    def revoke(self, *, provider_id: str, runtime_user_id: str) -> None:
        self._grant_store.revoke_grant(provider_id=provider_id, runtime_user_id=runtime_user_id)
        self._emit("remote_mcp.auth.revoked", {"provider_id": provider_id})

    def resolve_authorization_headers(
        self,
        *,
        server: MCPServerConfig,
        runtime_user_id: str,
        task_id: str,
        run_id: str,
    ) -> dict[str, str]:
        if server.auth.mode == "static_headers":
            return dict(server.headers)
        provider = self._provider(server)
        grant = self._grant_store.get_grant(
            provider_id=provider.provider_id,
            runtime_user_id=runtime_user_id,
        )
        if grant is None or grant.status != "authorized":
            raise AuthorizationRequiredError(
                _authorization_required_state(
                    server_name=server.name,
                    provider_id=provider.provider_id,
                    task_id=task_id,
                    run_id=run_id,
                )
            )
        if _is_expired(grant):
            if not grant.refresh_token:
                raise AuthorizationRequiredError(
                    _reauthorization_required_state(
                        server_name=server.name,
                        provider_id=provider.provider_id,
                        task_id=task_id,
                        run_id=run_id,
                    )
                )
            self._govern(
                "remote_mcp.auth.refresh",
                task_id=task_id,
                run_id=run_id,
                server_name=server.name,
                provider_id=provider.provider_id,
                target=_resolve_provider_endpoint(provider, "token"),
            )
            token_payload = self._token_client.refresh(provider, grant.refresh_token)
            grant = replace(
                _grant_from_token_payload(
                    provider_id=provider.provider_id,
                    runtime_user_id=runtime_user_id,
                    token_payload=token_payload,
                ),
                refresh_token=token_payload.get("refresh_token") or grant.refresh_token,
            )
            self._grant_store.save_grant(grant)
            self._emit("remote_mcp.auth.refreshed", {"server_name": server.name, "provider_id": provider.provider_id})
        return {"Authorization": f"Bearer {grant.access_token}"}

    def _server(self, server_name: str) -> MCPServerConfig:
        try:
            return self._mcp_config.servers[server_name]
        except KeyError as exc:
            raise KeyError(f"unknown MCP server: {server_name}") from exc

    def _provider(self, server: MCPServerConfig) -> OAuthProviderConfig:
        provider_id = server.auth.provider
        if provider_id is None:
            raise ValueError(f"MCP server {server.name} is not configured for oauth_user_grant")
        try:
            return self._mcp_config.oauth_providers[provider_id]
        except KeyError as exc:
            raise ValueError(f"unknown oauth provider: {provider_id}") from exc

    def _govern(
        self,
        operation_type: str,
        *,
        task_id: str | None,
        run_id: str | None,
        server_name: str,
        provider_id: str,
        target: str | None = None,
    ) -> None:
        if self._governed_operation is None or task_id is None or run_id is None:
            return
        self._governed_operation(
            OperationContext(
                task_id=task_id,
                run_id=run_id,
                operation_type=operation_type,
                path_scope=target,
                metadata={"server_name": server_name, "provider_id": provider_id},
            )
        )

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._on_event is not None:
            self._on_event(event_type, payload)


class RemoteMCPConnectionResolver:
    def __init__(self, auth_service: RemoteMCPAuthService | None = None) -> None:
        self._auth_service = auth_service

    def headers_for_server(
        self,
        *,
        server: MCPServerConfig,
        runtime_user_id: str | None,
        task_id: str,
        run_id: str,
    ) -> dict[str, str]:
        if server.auth.mode == "static_headers":
            return dict(server.headers)
        if runtime_user_id is None:
            raise AuthorizationRequiredError(
                _authorization_required_state(
                    server_name=server.name,
                    provider_id=server.auth.provider or "unknown",
                    task_id=task_id,
                    run_id=run_id,
                    summary="Remote MCP authorization requires runtime_user_id.",
                )
            )
        if self._auth_service is None:
            raise RuntimeError("Remote MCP auth service is not configured")
        return self._auth_service.resolve_authorization_headers(
            server=server,
            runtime_user_id=runtime_user_id,
            task_id=task_id,
            run_id=run_id,
        )


def _grant_from_token_payload(
    *,
    provider_id: str,
    runtime_user_id: str,
    token_payload: dict[str, Any],
) -> AuthorizedMCPGrant:
    access_token = token_payload.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise ValueError("OAuth token response did not include access_token")
    refresh_token = token_payload.get("refresh_token")
    token_type = token_payload.get("token_type") or "Bearer"
    scope_value = token_payload.get("scope") or ""
    expires_in = token_payload.get("expires_in")
    expires_at = None
    if isinstance(expires_in, int) and expires_in > 0:
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=expires_in)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return AuthorizedMCPGrant(
        provider_id=provider_id,
        runtime_user_id=runtime_user_id,
        access_token=access_token.strip(),
        refresh_token=refresh_token.strip() if isinstance(refresh_token, str) and refresh_token.strip() else None,
        token_type=str(token_type),
        scopes=tuple(item for item in str(scope_value).split(" ") if item),
        expires_at=expires_at,
    )


def _resolve_provider_endpoint(provider: OAuthProviderConfig, endpoint: str) -> str:
    if endpoint == "authorization" and provider.authorization_url is not None:
        return provider.authorization_url
    if endpoint == "token" and provider.token_url is not None:
        return provider.token_url
    if provider.discovery_url is None:
        raise ValueError(f"OAuth provider {provider.provider_id} has no {endpoint} endpoint")
    request = Request(provider.discovery_url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    key = "authorization_endpoint" if endpoint == "authorization" else "token_endpoint"
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"OAuth discovery for {provider.provider_id} did not include {key}")
    return value.strip()


def _is_expired(grant: AuthorizedMCPGrant) -> bool:
    if grant.expires_at is None:
        return False
    expires_at = datetime.fromisoformat(grant.expires_at.replace("Z", "+00:00"))
    return expires_at <= datetime.now(UTC)


def _authorization_required_state(
    *,
    server_name: str,
    provider_id: str,
    task_id: str,
    run_id: str,
    summary: str | None = None,
) -> RemoteMCPAuthorizationState:
    return RemoteMCPAuthorizationState(
        server_name=server_name,
        provider_id=provider_id,
        status="authorization_required",
        summary=summary or f"Remote MCP server {server_name} requires authorization for provider {provider_id}.",
        actions=(
            RemoteMCPActionDescriptor(
                action_id="authorize_remote_mcp",
                method=METHOD_REMOTE_MCP_AUTHORIZE_START,
                title="Authorize remote MCP",
                params={"task_id": task_id, "run_id": run_id, "server_name": server_name},
            ),
            RemoteMCPActionDescriptor(
                action_id="retry_remote_mcp_connect",
                method="task.resume",
                title="Retry after authorization",
                params={"task_id": task_id, "run_id": run_id},
            ),
        ),
    )


def _reauthorization_required_state(
    *,
    server_name: str,
    provider_id: str,
    task_id: str,
    run_id: str,
) -> RemoteMCPAuthorizationState:
    return RemoteMCPAuthorizationState(
        server_name=server_name,
        provider_id=provider_id,
        status="expired",
        summary=f"Remote MCP server {server_name} requires reauthorization for provider {provider_id}.",
        actions=(
            RemoteMCPActionDescriptor(
                action_id="reauthorize_remote_mcp",
                method=METHOD_REMOTE_MCP_REAUTHORIZE,
                title="Reauthorize remote MCP",
                params={"task_id": task_id, "run_id": run_id, "server_name": server_name},
            ),
            RemoteMCPActionDescriptor(
                action_id="complete_remote_mcp_authorization",
                method=METHOD_REMOTE_MCP_AUTHORIZE_COMPLETE,
                title="Complete remote MCP authorization",
                params={},
            ),
        ),
    )
