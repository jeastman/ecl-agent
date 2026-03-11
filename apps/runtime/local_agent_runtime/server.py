from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TextIO

from packages.config.local_agent_config.models import RuntimeConfig
from packages.identity.local_agent_identity.models import IdentityBundle
from packages.observability.local_agent_observability.logging import emit_event, log_record
from packages.protocol.local_agent_protocol.models import (
    EventEnvelope,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    RuntimeHealthResult,
    TaskSubmitParams,
    TaskSubmitResult,
)
from packages.task_model.local_agent_task_model.ids import new_event_id, new_run_id, new_task_id
from packages.task_model.local_agent_task_model.models import (
    ActionDescriptor,
    TaskSnapshot,
    TaskStatus,
)


@dataclass(slots=True)
class RuntimeServer:
    config: RuntimeConfig
    identity: IdentityBundle

    def serve(self, reader: TextIO, writer: TextIO) -> int:
        for raw_line in reader:
            line = raw_line.strip()
            if not line:
                continue
            response = self.handle_line(line)
            writer.write(json.dumps(response.to_dict()) + "\n")
            writer.flush()
        return 0

    def handle_line(self, line: str) -> JsonRpcResponse:
        try:
            request = JsonRpcRequest.from_dict(json.loads(line))
        except (json.JSONDecodeError, ValueError) as exc:
            return JsonRpcResponse(
                id=None,
                correlation_id=None,
                error=JsonRpcError(code=-32700, message=f"invalid request: {exc}"),
            )

        correlation_id = request.correlation_id
        log_record(
            level="info",
            message=f"handling {request.method}",
            correlation_id=correlation_id,
            method=request.method,
        )

        try:
            result: RuntimeHealthResult | TaskSubmitResult
            if request.method == "runtime.health":
                result = self.runtime_health(correlation_id)
            elif request.method == "task.submit":
                result = self.task_submit(request.params, correlation_id)
            else:
                return JsonRpcResponse(
                    id=request.id,
                    correlation_id=correlation_id,
                    error=JsonRpcError(code=-32601, message=f"unknown method: {request.method}"),
                )
            return JsonRpcResponse(id=request.id, correlation_id=correlation_id, result=result)
        except ValueError as exc:
            return JsonRpcResponse(
                id=request.id,
                correlation_id=correlation_id,
                error=JsonRpcError(code=-32602, message=str(exc)),
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

    def runtime_health(self, correlation_id: str | None) -> RuntimeHealthResult:
        return RuntimeHealthResult(
            runtime_name=self.config.runtime.name,
            runtime_version="0.1.0",
            status="ok",
            transport=self.config.transport.mode,
            correlation_id=correlation_id,
            identity={
                "path": self.identity.source_path,
                "version": self.identity.version,
                "sha256": self.identity.sha256,
            },
        )

    def task_submit(self, params: dict[str, Any], correlation_id: str | None) -> TaskSubmitResult:
        request = TaskSubmitParams.from_dict(params)

        task = TaskSnapshot(
            task_id=new_task_id(),
            run_id=new_run_id(),
            status=TaskStatus.ACCEPTED,
            objective=request.objective,
            constraints=request.constraints,
            success_criteria=request.success_criteria,
            available_actions=[
                ActionDescriptor(
                    action="task.inspect",
                    label="Inspect task",
                    description="Retrieve the latest task snapshot.",
                )
            ],
        )

        event = EventEnvelope(
            event_id=new_event_id(),
            event_type="task.accepted",
            correlation_id=correlation_id,
            task_id=task.task_id,
            run_id=task.run_id,
            payload=task.to_dict(),
        )
        emit_event(event)
        log_record(
            level="info",
            message="task accepted",
            correlation_id=correlation_id,
            task_id=task.task_id,
            run_id=task.run_id,
        )

        return TaskSubmitResult(
            correlation_id=correlation_id,
            message="Task accepted by runtime shell. Execution remains stubbed in Milestone 0.",
            task=task,
        )
