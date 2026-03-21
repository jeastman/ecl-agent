from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.callbacks import Callbacks
from langchain_mcp_adapters.tools import load_mcp_tools
from pydantic import ValidationError

from packages.config.local_agent_config.models import MCPConfig, MCPServerConfig
from services.policy_service.local_agent_policy_service.policy_models import OperationContext
from services.remote_mcp_auth_service import RemoteMCPConnectionResolver

EventCallback = Callable[[str, dict[str, Any]], None]

_MCP_CAPABILITY_ALIASES = {"mcp_tools", "mcp", "mcp.tools"}


@dataclass(slots=True)
class MCPToolProvider:
    config: MCPConfig
    task_id: str
    run_id: str
    runtime_user_id: str | None = None
    allowed_capabilities: list[str] | None = None
    governed_operation: Callable[[OperationContext], None] | None = None
    on_event: EventCallback | None = None
    connection_resolver: RemoteMCPConnectionResolver | None = None
    _session_tools: dict[str, list[BaseTool]] = field(default_factory=dict)
    _role_cache: dict[str, list[BaseTool]] = field(default_factory=dict)
    _started: bool = False

    def is_enabled_for_run(self) -> bool:
        enabled_servers = any(server.enabled for server in self.config.servers.values())
        if not enabled_servers:
            return False
        allowed = {item.strip() for item in self.allowed_capabilities or [] if item.strip()}
        if not allowed:
            return True
        return not allowed.isdisjoint(_MCP_CAPABILITY_ALIASES)

    def start(self) -> None:
        if self._started or not self.is_enabled_for_run():
            return
        asyncio.run(self._startup())
        self._started = True

    def close(self) -> None:
        self._session_tools.clear()
        self._role_cache.clear()
        self._started = False

    def tools_for_role(self, role: str) -> list[BaseTool]:
        if not self._started:
            self.start()
        cached = self._role_cache.get(role)
        if cached is not None:
            return list(cached)
        tools: list[BaseTool] = []
        for server_name, raw_tools in self._session_tools.items():
            server = self.config.servers[server_name]
            for raw_tool in raw_tools:
                tools.append(self._wrap_tool(role=role, server=server, raw_tool=raw_tool))
        self._role_cache[role] = tools
        return list(tools)

    async def _startup(self) -> None:
        callbacks = Callbacks(
            on_logging_message=self._on_logging_message,
            on_progress=self._on_progress,
            on_elicitation=self._on_elicitation,
        )
        for server_name, server in self.config.servers.items():
            if not server.enabled:
                continue
            self._govern_server_connect(server)
            self._session_tools[server_name] = await load_mcp_tools(
                None,
                connection=self._connection_payload(server),
                callbacks=callbacks,
                server_name=server_name,
                tool_name_prefix=self.config.tool_name_prefix,
            )

    def _govern_server_connect(self, server: MCPServerConfig) -> None:
        if self.governed_operation is None:
            return
        target = server.url if server.url is not None else server.command or server.name
        self.governed_operation(
            OperationContext(
                task_id=self.task_id,
                run_id=self.run_id,
                operation_type="mcp.server.connect",
                path_scope=target,
                metadata={
                    "server_name": server.name,
                    "transport": server.transport,
                    "source": server.source,
                    "source_path": server.source_path,
                    "command": server.command,
                    "url": server.url,
                },
            )
        )

    async def _on_logging_message(self, params: Any, context: Any) -> None:
        self._emit(
            "mcp.log",
            {
                "server_name": context.server_name,
                "level": str(getattr(params, "level", "info")).lower(),
                "message": getattr(params, "data", None),
                "logger": getattr(params, "logger", None),
            },
        )

    async def _on_progress(
        self,
        progress: float,
        total: float | None,
        message: str | None,
        context: Any,
    ) -> None:
        self._emit(
            "mcp.progress",
            {
                "server_name": context.server_name,
                "tool_name": context.tool_name,
                "progress": progress,
                "total": total,
                "message": message,
            },
        )

    async def _on_elicitation(self, _mcp_context: Any, params: Any, context: Any) -> Any:
        self._emit(
            "mcp.elicitation.unsupported",
            {
                "server_name": context.server_name,
                "tool_name": context.tool_name,
                "message": getattr(params, "message", None),
            },
        )
        raise RuntimeError("MCP elicitation is not supported by this runtime")

    def _wrap_tool(self, *, role: str, server: MCPServerConfig, raw_tool: BaseTool) -> BaseTool:
        exposed_name = raw_tool.name
        original_name = _original_tool_name(
            exposed_name,
            server_name=server.name,
            tool_name_prefix=self.config.tool_name_prefix,
        )

        def _invoke(**arguments: Any) -> Any:
            self._emit_tool_called(
                role=role,
                server=server,
                raw_tool_name=original_name,
                exposed_tool_name=exposed_name,
                arguments=arguments,
            )
            try:
                return asyncio.run(raw_tool.ainvoke(arguments))
            except ValidationError as exc:
                return self._handle_validation_error(
                    role=role,
                    server=server,
                    raw_tool_name=original_name,
                    exposed_tool_name=exposed_name,
                    exc=exc,
                )
            except Exception as exc:
                return self._handle_execution_error(
                    role=role,
                    server=server,
                    raw_tool_name=original_name,
                    exposed_tool_name=exposed_name,
                    arguments=arguments,
                    exc=exc,
                )

        async def _ainvoke(**arguments: Any) -> Any:
            self._emit_tool_called(
                role=role,
                server=server,
                raw_tool_name=original_name,
                exposed_tool_name=exposed_name,
                arguments=arguments,
            )
            try:
                return await raw_tool.ainvoke(arguments)
            except ValidationError as exc:
                return self._handle_validation_error(
                    role=role,
                    server=server,
                    raw_tool_name=original_name,
                    exposed_tool_name=exposed_name,
                    exc=exc,
                )
            except Exception as exc:
                return self._handle_execution_error(
                    role=role,
                    server=server,
                    raw_tool_name=original_name,
                    exposed_tool_name=exposed_name,
                    arguments=arguments,
                    exc=exc,
                )

        return StructuredTool(
            name=exposed_name,
            description=raw_tool.description,
            args_schema=raw_tool.args_schema,
            response_format="content",
            handle_validation_error=lambda exc: self._handle_validation_error(
                role=role,
                server=server,
                raw_tool_name=original_name,
                exposed_tool_name=exposed_name,
                exc=exc,
            ),
            metadata={
                **(raw_tool.metadata or {}),
                "mcp": {
                    "server_name": server.name,
                    "transport": server.transport,
                    "tool_name": original_name,
                    "source": server.source,
                },
            },
            func=_invoke,
            coroutine=_ainvoke,
        )

    def _handle_validation_error(
        self,
        *,
        role: str,
        server: MCPServerConfig,
        raw_tool_name: str,
        exposed_tool_name: str,
        exc: ValidationError | Any,
    ) -> str:
        details = exc.errors() if hasattr(exc, "errors") else []
        message = str(exc)
        self._emit(
            "tool.rejected",
            {
                "tool": exposed_tool_name,
                "arguments": {},
                "server_name": server.name,
                "transport": server.transport,
                "raw_tool_name": raw_tool_name,
                "exposed_tool_name": exposed_tool_name,
                "tool_source": "mcp",
                "agent_role": role,
                "code": "invalid_arguments",
                "category": "argument_validation",
                "message": message,
                "retryable": True,
                "details": {"errors": details},
                "summary": f"{exposed_tool_name} rejected: {message}",
            },
        )
        return (
            f"TOOL_REJECTED [invalid_arguments]: {message} "
            "Adjust the tool arguments to satisfy the schema and try again."
        )

    def _handle_execution_error(
        self,
        *,
        role: str,
        server: MCPServerConfig,
        raw_tool_name: str,
        exposed_tool_name: str,
        arguments: dict[str, Any],
        exc: Exception,
    ) -> str:
        message = str(exc)
        self._emit(
            "tool.rejected",
            {
                "tool": exposed_tool_name,
                "arguments": _sanitize_mcp_arguments(arguments),
                "server_name": server.name,
                "transport": server.transport,
                "raw_tool_name": raw_tool_name,
                "exposed_tool_name": exposed_tool_name,
                "tool_source": "mcp",
                "agent_role": role,
                "code": "tool_execution_failed",
                "category": "tool_execution",
                "message": message,
                "retryable": True,
                "details": {},
                "summary": f"{exposed_tool_name} rejected: {message}",
            },
        )
        return (
            f"TOOL_REJECTED [tool_execution_failed]: {message} "
            "Revise the tool arguments or query syntax and try again."
        )

    def _emit_tool_called(
        self,
        *,
        role: str,
        server: MCPServerConfig,
        raw_tool_name: str,
        exposed_tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        self._emit(
            "tool.called",
            {
                "tool": exposed_tool_name,
                "arguments": arguments,
                "server_name": server.name,
                "transport": server.transport,
                "raw_tool_name": raw_tool_name,
                "exposed_tool_name": exposed_tool_name,
                "tool_source": "mcp",
                "agent_role": role,
            },
        )

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.on_event is not None:
            self.on_event(event_type, payload)

    def _connection_payload(self, server: MCPServerConfig) -> dict[str, Any]:
        if server.transport == "stdio":
            return _connection_payload(server)
        payload = _connection_payload(server)
        if self.connection_resolver is not None:
            payload["headers"] = self.connection_resolver.headers_for_server(
                server=server,
                runtime_user_id=self.runtime_user_id,
                task_id=self.task_id,
                run_id=self.run_id,
            )
        return payload



def _connection_payload(server: MCPServerConfig) -> dict[str, Any]:
    if server.transport == "stdio":
        payload: dict[str, Any] = {
            "transport": "stdio",
            "command": server.command,
        }
        if server.args:
            payload["args"] = list(server.args)
        env_payload = dict(server.env)
        for variable_name in server.env_from_host:
            env_payload.setdefault(variable_name, os.environ[variable_name])
        if env_payload:
            payload["env"] = env_payload
        return payload
    payload = {
        "transport": server.transport,
        "url": server.url,
    }
    if server.headers:
        payload["headers"] = dict(server.headers)
    return payload


def _sanitize_mcp_arguments(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return "<host-native-path>" if stripped.startswith("/") and not stripped.startswith("/workspace") and not stripped.startswith("/tmp") and not stripped.startswith("/.memory") else value
    if isinstance(value, list):
        return [_sanitize_mcp_arguments(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_mcp_arguments(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_mcp_arguments(item) for key, item in value.items()}
    return value


def _original_tool_name(tool_name: str, *, server_name: str, tool_name_prefix: bool) -> str:
    prefix = f"{server_name}_"
    if tool_name_prefix and tool_name.startswith(prefix):
        return tool_name[len(prefix) :]
    return tool_name
