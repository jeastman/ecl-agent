from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from packages.task_model.local_agent_task_model.models import TaskSnapshot


@dataclass(slots=True)
class JsonRpcRequest:
    method: str
    params: dict[str, Any]
    id: str | int | None = None
    jsonrpc: str = "2.0"
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.correlation_id is None:
            payload.pop("correlation_id")
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JsonRpcRequest":
        if payload.get("jsonrpc") != "2.0":
            raise ValueError("jsonrpc must be 2.0")
        method = payload.get("method")
        if not isinstance(method, str) or not method:
            raise ValueError("method must be a non-empty string")
        params = payload.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("params must be an object")
        return cls(
            method=method,
            params=params,
            id=payload.get("id"),
            correlation_id=payload.get("correlation_id"),
        )


@dataclass(slots=True)
class JsonRpcError:
    code: int
    message: str
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {"code": self.code, "message": self.message}
        if self.data is not None:
            payload["data"] = self.data
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JsonRpcError":
        return cls(
            code=int(payload["code"]), message=str(payload["message"]), data=payload.get("data")
        )


@dataclass(slots=True)
class JsonRpcResponse:
    id: str | int | None
    correlation_id: str | None
    result: Any = None
    error: JsonRpcError | None = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.correlation_id is not None:
            payload["correlation_id"] = self.correlation_id
        if self.error is not None:
            payload["error"] = self.error.to_dict()
        else:
            payload["result"] = (
                self.result.to_dict() if hasattr(self.result, "to_dict") else self.result
            )
        return payload


@dataclass(slots=True)
class TaskSubmitParams:
    objective: str
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskSubmitParams":
        objective = str(payload.get("objective", "")).strip()
        if not objective:
            raise ValueError("task.submit requires a non-empty objective")
        constraints = payload.get("constraints", [])
        success_criteria = payload.get("success_criteria", [])
        if not isinstance(constraints, list) or not all(
            isinstance(item, str) for item in constraints
        ):
            raise ValueError("constraints must be a list of strings")
        if not isinstance(success_criteria, list) or not all(
            isinstance(item, str) for item in success_criteria
        ):
            raise ValueError("success_criteria must be a list of strings")
        return cls(
            objective=objective,
            constraints=constraints,
            success_criteria=success_criteria,
        )


@dataclass(slots=True)
class EventEnvelope:
    event_id: str
    event_type: str
    correlation_id: str | None
    task_id: str | None
    run_id: str | None
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RuntimeHealthResult:
    runtime_name: str
    runtime_version: str
    status: str
    transport: str
    correlation_id: str | None
    identity: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TaskSubmitResult:
    correlation_id: str | None
    message: str
    task: TaskSnapshot | dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if isinstance(self.task, TaskSnapshot):
            payload["task"] = self.task.to_dict()
        return payload
