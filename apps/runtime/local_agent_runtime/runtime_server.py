from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TextIO

from apps.runtime.local_agent_runtime.method_handlers import MethodHandlers
from packages.observability.local_agent_observability.logging import log_record
from packages.protocol.local_agent_protocol.models import (
    METHOD_MEMORY_INSPECT,
    METHOD_RUNTIME_HEALTH,
    METHOD_TASK_ARTIFACTS_LIST,
    METHOD_TASK_CREATE,
    METHOD_TASK_GET,
    METHOD_TASK_RESUME,
    METHOD_TASK_LOGS_STREAM,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    RuntimeEvent,
)


@dataclass(slots=True)
class RuntimeServer:
    handlers: MethodHandlers

    def serve(self, reader: TextIO, writer: TextIO) -> int:
        for raw_line in reader:
            line = raw_line.strip()
            if not line:
                continue
            response, streamed_events = self.handle_line(line)
            writer.write(json.dumps(response.to_dict()) + "\n")
            for event in streamed_events:
                writer.write(json.dumps(event.to_dict()) + "\n")
            writer.flush()
        return 0

    def handle_line(self, line: str) -> tuple[JsonRpcResponse, list[RuntimeEvent]]:
        try:
            request = JsonRpcRequest.from_dict(json.loads(line))
        except (json.JSONDecodeError, ValueError) as exc:
            return (
                JsonRpcResponse(
                    id=None,
                    correlation_id=None,
                    error=JsonRpcError(code=-32700, message=f"invalid request: {exc}"),
                ),
                [],
            )

        correlation_id = request.correlation_id
        log_record(
            level="info",
            message=f"handling {request.method}",
            correlation_id=correlation_id,
            method=request.method,
        )

        try:
            if request.method == METHOD_RUNTIME_HEALTH:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.runtime_health(correlation_id),
                    ),
                    [],
                )
            if request.method == METHOD_TASK_CREATE:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.task_create(request.params, correlation_id),
                    ),
                    [],
                )
            if request.method == METHOD_TASK_GET:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.task_get(request.params),
                    ),
                    [],
                )
            if request.method == METHOD_TASK_RESUME:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.task_resume(request.params),
                    ),
                    [],
                )
            if request.method == METHOD_TASK_ARTIFACTS_LIST:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.task_artifacts_list(request.params),
                    ),
                    [],
                )
            if request.method == METHOD_TASK_LOGS_STREAM:
                result, events = self.handlers.task_logs_stream(request.params)
                return JsonRpcResponse(
                    id=request.id, correlation_id=correlation_id, result=result
                ), events
            if request.method == METHOD_MEMORY_INSPECT:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.memory_inspect(request.params),
                    ),
                    [],
                )
            return (
                JsonRpcResponse(
                    id=request.id,
                    correlation_id=correlation_id,
                    error=JsonRpcError(code=-32601, message=f"unknown method: {request.method}"),
                ),
                [],
            )
        except ValueError as exc:
            return (
                JsonRpcResponse(
                    id=request.id,
                    correlation_id=correlation_id,
                    error=JsonRpcError(code=-32602, message=str(exc)),
                ),
                [],
            )
        except KeyError as exc:
            return (
                JsonRpcResponse(
                    id=request.id,
                    correlation_id=correlation_id,
                    error=JsonRpcError(code=-32004, message=str(exc)),
                ),
                [],
            )
        except Exception as exc:  # pragma: no cover
            log_record(
                level="error",
                message="unhandled runtime failure",
                correlation_id=correlation_id,
                error=str(exc),
            )
            return (
                JsonRpcResponse(
                    id=request.id,
                    correlation_id=correlation_id,
                    error=JsonRpcError(
                        code=-32000, message="runtime failure", data={"detail": str(exc)}
                    ),
                ),
                [],
            )
