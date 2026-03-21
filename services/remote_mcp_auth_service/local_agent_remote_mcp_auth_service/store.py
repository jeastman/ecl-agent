from __future__ import annotations

import sqlite3
from dataclasses import replace
from threading import RLock
from typing import Protocol

from services.remote_mcp_auth_service.local_agent_remote_mcp_auth_service.models import (
    AuthorizedMCPGrant,
    PendingOAuthAuthorization,
)


class RemoteMCPGrantStore(Protocol):
    def save_grant(self, grant: AuthorizedMCPGrant) -> None: ...
    def get_grant(self, *, provider_id: str, runtime_user_id: str) -> AuthorizedMCPGrant | None: ...
    def revoke_grant(self, *, provider_id: str, runtime_user_id: str) -> None: ...
    def save_pending_authorization(self, authorization: PendingOAuthAuthorization) -> None: ...
    def get_pending_authorization(self, authorization_id: str) -> PendingOAuthAuthorization | None: ...
    def delete_pending_authorization(self, authorization_id: str) -> None: ...


class InMemoryRemoteMCPGrantStore:
    def __init__(self) -> None:
        self._grants: dict[tuple[str, str], AuthorizedMCPGrant] = {}
        self._pending: dict[str, PendingOAuthAuthorization] = {}
        self._lock = RLock()

    def save_grant(self, grant: AuthorizedMCPGrant) -> None:
        with self._lock:
            self._grants[(grant.provider_id, grant.runtime_user_id)] = grant

    def get_grant(self, *, provider_id: str, runtime_user_id: str) -> AuthorizedMCPGrant | None:
        with self._lock:
            return self._grants.get((provider_id, runtime_user_id))

    def revoke_grant(self, *, provider_id: str, runtime_user_id: str) -> None:
        with self._lock:
            grant = self._grants.get((provider_id, runtime_user_id))
            if grant is not None:
                self._grants[(provider_id, runtime_user_id)] = replace(grant, status="revoked")

    def save_pending_authorization(self, authorization: PendingOAuthAuthorization) -> None:
        with self._lock:
            self._pending[authorization.authorization_id] = authorization

    def get_pending_authorization(self, authorization_id: str) -> PendingOAuthAuthorization | None:
        with self._lock:
            return self._pending.get(authorization_id)

    def delete_pending_authorization(self, authorization_id: str) -> None:
        with self._lock:
            self._pending.pop(authorization_id, None)


class SQLiteRemoteMCPGrantStore:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS remote_mcp_grants (
                    provider_id TEXT NOT NULL,
                    runtime_user_id TEXT NOT NULL,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    token_type TEXT NOT NULL,
                    scopes TEXT NOT NULL,
                    expires_at TEXT,
                    account_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    PRIMARY KEY (provider_id, runtime_user_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS remote_mcp_pending_authorizations (
                    authorization_id TEXT PRIMARY KEY,
                    server_name TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    runtime_user_id TEXT NOT NULL,
                    state_token TEXT NOT NULL,
                    authorization_url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    task_id TEXT,
                    run_id TEXT
                )
                """
            )

    def save_grant(self, grant: AuthorizedMCPGrant) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO remote_mcp_grants
                (provider_id, runtime_user_id, access_token, refresh_token, token_type, scopes, expires_at, account_key, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_id, runtime_user_id) DO UPDATE SET
                  access_token=excluded.access_token,
                  refresh_token=excluded.refresh_token,
                  token_type=excluded.token_type,
                  scopes=excluded.scopes,
                  expires_at=excluded.expires_at,
                  account_key=excluded.account_key,
                  status=excluded.status
                """,
                (
                    grant.provider_id,
                    grant.runtime_user_id,
                    grant.access_token,
                    grant.refresh_token,
                    grant.token_type,
                    " ".join(grant.scopes),
                    grant.expires_at,
                    grant.account_key,
                    grant.status,
                ),
            )

    def get_grant(self, *, provider_id: str, runtime_user_id: str) -> AuthorizedMCPGrant | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT provider_id, runtime_user_id, access_token, refresh_token, token_type, scopes, expires_at, account_key, status
                FROM remote_mcp_grants
                WHERE provider_id = ? AND runtime_user_id = ?
                """,
                (provider_id, runtime_user_id),
            ).fetchone()
        if row is None:
            return None
        scopes = tuple(item for item in str(row["scopes"]).split(" ") if item)
        return AuthorizedMCPGrant(
            provider_id=str(row["provider_id"]),
            runtime_user_id=str(row["runtime_user_id"]),
            access_token=str(row["access_token"]),
            refresh_token=str(row["refresh_token"]) if row["refresh_token"] is not None else None,
            token_type=str(row["token_type"]),
            scopes=scopes,
            expires_at=str(row["expires_at"]) if row["expires_at"] is not None else None,
            account_key=str(row["account_key"]),
            status=str(row["status"]),
        )

    def revoke_grant(self, *, provider_id: str, runtime_user_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE remote_mcp_grants
                SET status = 'revoked'
                WHERE provider_id = ? AND runtime_user_id = ?
                """,
                (provider_id, runtime_user_id),
            )

    def save_pending_authorization(self, authorization: PendingOAuthAuthorization) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO remote_mcp_pending_authorizations
                (authorization_id, server_name, provider_id, runtime_user_id, state_token, authorization_url, created_at, task_id, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    authorization.authorization_id,
                    authorization.server_name,
                    authorization.provider_id,
                    authorization.runtime_user_id,
                    authorization.state_token,
                    authorization.authorization_url,
                    authorization.created_at,
                    authorization.task_id,
                    authorization.run_id,
                ),
            )

    def get_pending_authorization(self, authorization_id: str) -> PendingOAuthAuthorization | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT authorization_id, server_name, provider_id, runtime_user_id, state_token, authorization_url, created_at, task_id, run_id
                FROM remote_mcp_pending_authorizations
                WHERE authorization_id = ?
                """,
                (authorization_id,),
            ).fetchone()
        if row is None:
            return None
        return PendingOAuthAuthorization(
            authorization_id=str(row["authorization_id"]),
            server_name=str(row["server_name"]),
            provider_id=str(row["provider_id"]),
            runtime_user_id=str(row["runtime_user_id"]),
            state_token=str(row["state_token"]),
            authorization_url=str(row["authorization_url"]),
            created_at=str(row["created_at"]),
            task_id=str(row["task_id"]) if row["task_id"] is not None else None,
            run_id=str(row["run_id"]) if row["run_id"] is not None else None,
        )

    def delete_pending_authorization(self, authorization_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM remote_mcp_pending_authorizations WHERE authorization_id = ?",
                (authorization_id,),
            )
