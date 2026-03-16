from __future__ import annotations

import json
from dataclasses import dataclass
from queue import Empty
from threading import Event, Lock, Thread
from typing import Callable, TextIO

from apps.runtime.local_agent_runtime.method_handlers import MethodHandlers
from packages.observability.local_agent_observability.logging import log_record
from packages.protocol.local_agent_protocol.models import (
    METHOD_CONFIG_GET,
    METHOD_MEMORY_INSPECT,
    METHOD_RUNTIME_HEALTH,
    METHOD_SKILL_INSTALL,
    METHOD_TASK_APPROVE,
    METHOD_TASK_APPROVALS_LIST,
    METHOD_TASK_ARTIFACT_GET,
    METHOD_TASK_ARTIFACTS_LIST,
    METHOD_TASK_CREATE,
    METHOD_TASK_DIAGNOSTICS_LIST,
    METHOD_TASK_GET,
    METHOD_TASK_LIST,
    METHOD_TASK_LOGS_STREAM,
    METHOD_TASK_REPLY,
    METHOD_TASK_RESUME,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    RuntimeEvent,
)


@dataclass(slots=True)
class RuntimeServer:
    handlers: MethodHandlers

    def serve(self, reader: TextIO, writer: TextIO) -> int:
        write_lock = Lock()
        session_closed = Event()
        request_threads: list[Thread] = []

        for raw_line in reader:
            line = raw_line.strip()
            if not line:
                continue
            worker = Thread(
                target=self._serve_request,
                kwargs={
                    "line": line,
                    "writer": writer,
                    "write_lock": write_lock,
                    "session_closed": session_closed,
                },
            )
            worker.start()
            request_threads.append(worker)

        session_closed.set()
        self.handlers.task_runner.wait_for_all_runs()
        for worker in request_threads:
            worker.join()
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
        return self._dispatch_request(request)

    def _dispatch_request(
        self, request: JsonRpcRequest
    ) -> tuple[JsonRpcResponse, list[RuntimeEvent]]:
        correlation_id = request.correlation_id

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
            if request.method == METHOD_TASK_LIST:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.task_list(request.params),
                    ),
                    [],
                )
            if request.method == METHOD_TASK_APPROVE:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.task_approve(request.params),
                    ),
                    [],
                )
            if request.method == METHOD_TASK_APPROVALS_LIST:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.task_approvals_list(request.params),
                    ),
                    [],
                )
            if request.method == METHOD_TASK_DIAGNOSTICS_LIST:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.task_diagnostics_list(request.params),
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
            if request.method == METHOD_TASK_REPLY:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.task_reply(request.params),
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
            if request.method == METHOD_TASK_ARTIFACT_GET:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.task_artifact_get(request.params),
                    ),
                    [],
                )
            if request.method == METHOD_TASK_LOGS_STREAM:
                result, events = self.handlers.task_logs_stream(request.params)
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=result,
                    ),
                    events,
                )
            if request.method == METHOD_MEMORY_INSPECT:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.memory_inspect(request.params),
                    ),
                    [],
                )
            if request.method == METHOD_SKILL_INSTALL:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.skill_install(request.params, correlation_id),
                    ),
                    [],
                )
            if request.method == METHOD_CONFIG_GET:
                return (
                    JsonRpcResponse(
                        id=request.id,
                        correlation_id=correlation_id,
                        result=self.handlers.config_get(),
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

    def _serve_request(
        self,
        *,
        line: str,
        writer: TextIO,
        write_lock: Lock,
        session_closed: Event,
    ) -> None:
        try:
            request = JsonRpcRequest.from_dict(json.loads(line))
        except (json.JSONDecodeError, ValueError) as exc:
            self._write_payload(
                writer,
                write_lock,
                JsonRpcResponse(
                    id=None,
                    correlation_id=None,
                    error=JsonRpcError(code=-32700, message=f"invalid request: {exc}"),
                ).to_dict(),
            )
            return

        correlation_id = request.correlation_id
        log_record(
            level="info",
            message=f"handling {request.method}",
            correlation_id=correlation_id,
            method=request.method,
        )

        if request.method == METHOD_TASK_LOGS_STREAM:
            self._serve_logs_stream(
                request=request,
                writer=writer,
                write_lock=write_lock,
                session_closed=session_closed,
            )
            return

        if request.method == METHOD_TASK_CREATE:
            response = self._background_response(
                request,
                lambda: self.handlers.task_create(
                    request.params,
                    correlation_id,
                    background=True,
                ),
            )
            self._write_payload(writer, write_lock, response.to_dict())
            return

        if request.method == METHOD_TASK_RESUME:
            response = self._background_response(
                request,
                lambda: self.handlers.task_resume(request.params, background=True),
            )
            self._write_payload(writer, write_lock, response.to_dict())
            return

        response, streamed_events = self._dispatch_request(request)
        self._write_payload(writer, write_lock, response.to_dict())
        for event in streamed_events:
            self._write_payload(writer, write_lock, event.to_dict())

    def _serve_logs_stream(
        self,
        *,
        request: JsonRpcRequest,
        writer: TextIO,
        write_lock: Lock,
        session_closed: Event,
    ) -> None:
        correlation_id = request.correlation_id
        response, history = self._dispatch_request(request)
        self._write_payload(writer, write_lock, response.to_dict())
        if response.error is not None:
            return
        for event in history:
            self._write_payload(writer, write_lock, event.to_dict())
        if history and _is_terminal_event(history[-1]):
            return

        result = response.to_dict()["result"]
        task_id = str(result["task_id"])
        run_id = str(result["run_id"])
        seen_event_ids = {event.event.event_id for event in history}
        from_event_id = history[-1].event.event_id if history else None
        with self.handlers.event_bus.subscribe(task_id, run_id) as subscription:
            for event in self.handlers.event_bus.list_events(
                task_id,
                run_id,
                from_event_id=from_event_id,
            ):
                if event.event.event_id in seen_event_ids:
                    continue
                seen_event_ids.add(event.event.event_id)
                self._write_payload(writer, write_lock, event.to_dict())
                if _is_terminal_event(event):
                    return
            while not session_closed.is_set():
                try:
                    event = subscription.get(timeout=0.1)
                except Empty:
                    continue
                if event.event.event_id in seen_event_ids:
                    continue
                seen_event_ids.add(event.event.event_id)
                self._write_payload(writer, write_lock, event.to_dict())
                if _is_terminal_event(event):
                    return

        log_record(
            level="info",
            message="closing logs stream",
            correlation_id=correlation_id,
            method=request.method,
        )

    def _write_payload(self, writer: TextIO, write_lock: Lock, payload: dict) -> None:
        with write_lock:
            writer.write(json.dumps(payload) + "\n")
            writer.flush()

    def _background_response(
        self,
        request: JsonRpcRequest,
        action: Callable[[], object],
    ) -> JsonRpcResponse:
        correlation_id = request.correlation_id
        try:
            return JsonRpcResponse(
                id=request.id,
                correlation_id=correlation_id,
                result=action(),
            )
        except ValueError as exc:
            return JsonRpcResponse(
                id=request.id,
                correlation_id=correlation_id,
                error=JsonRpcError(code=-32602, message=str(exc)),
            )
        except KeyError as exc:
            return JsonRpcResponse(
                id=request.id,
                correlation_id=correlation_id,
                error=JsonRpcError(code=-32004, message=str(exc)),
            )
        except Exception as exc:  # pragma: no cover
            log_record(
                level="error",
                message="unhandled runtime failure",
                correlation_id=correlation_id,
                error=str(exc),
            )
            return JsonRpcResponse(
                id=request.id,
                correlation_id=correlation_id,
                error=JsonRpcError(
                    code=-32000, message="runtime failure", data={"detail": str(exc)}
                ),
            )


def _is_terminal_event(event: RuntimeEvent) -> bool:
    return event.event.event_type in {"task.completed", "task.failed"}
