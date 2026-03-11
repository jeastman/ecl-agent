from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from packages.task_model.local_agent_task_model.models import FailureInfo, TaskStatus

PROTOCOL_VERSION = "1.0.0"

METHOD_RUNTIME_HEALTH = "runtime.health"
METHOD_TASK_CREATE = "task.create"
METHOD_TASK_GET = "task.get"
METHOD_TASK_LOGS_STREAM = "task.logs.stream"
METHOD_TASK_ARTIFACTS_LIST = "task.artifacts.list"


def utc_now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


class EventSourceKind(StrEnum):
    RUNTIME = "runtime"
    SUBAGENT = "subagent"
    TOOL = "tool"
    SANDBOX = "sandbox"
    MEMORY = "memory"
    POLICY = "policy"


@dataclass(slots=True)
class EventSource:
    kind: EventSourceKind
    name: str | None = None
    role: str | None = None
    component: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {"kind": self.kind.value}
        if self.name is not None:
            payload["name"] = self.name
        if self.role is not None:
            payload["role"] = self.role
        if self.component is not None:
            payload["component"] = self.component
        return payload


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
            code=int(payload["code"]),
            message=str(payload["message"]),
            data=payload.get("data"),
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
class TaskCreateRequest:
    objective: str
    workspace_roots: list[str] = field(default_factory=list)
    scope: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    allowed_capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskCreateRequest":
        objective = str(payload.get("objective", "")).strip()
        if not objective:
            raise ValueError("task.create requires task.objective")
        workspace_roots = payload.get("workspace_roots", [])
        scope = payload.get("scope", [])
        success_criteria = payload.get("success_criteria", [])
        constraints = payload.get("constraints", [])
        allowed_capabilities = payload.get("allowed_capabilities", [])
        metadata = payload.get("metadata", {})
        if not isinstance(workspace_roots, list) or not all(
            isinstance(item, str) and item.strip() for item in workspace_roots
        ):
            raise ValueError("task.workspace_roots must be a list of non-empty strings")
        if not workspace_roots:
            raise ValueError("task.create requires task.workspace_roots")
        if not isinstance(scope, list) or not all(isinstance(item, str) for item in scope):
            raise ValueError("task.scope must be a list of strings")
        if not isinstance(success_criteria, list) or not all(
            isinstance(item, str) for item in success_criteria
        ):
            raise ValueError("task.success_criteria must be a list of strings")
        if not isinstance(constraints, list) or not all(
            isinstance(item, str) for item in constraints
        ):
            raise ValueError("task.constraints must be a list of strings")
        if not isinstance(allowed_capabilities, list) or not all(
            isinstance(item, str) for item in allowed_capabilities
        ):
            raise ValueError("task.allowed_capabilities must be a list of strings")
        if not isinstance(metadata, dict):
            raise ValueError("task.metadata must be an object")
        return cls(
            objective=objective,
            workspace_roots=workspace_roots,
            scope=scope,
            success_criteria=success_criteria,
            constraints=constraints,
            allowed_capabilities=allowed_capabilities,
            metadata=metadata,
        )


@dataclass(slots=True)
class TaskCreateParams:
    task: TaskCreateRequest

    def to_dict(self) -> dict[str, Any]:
        return {"task": self.task.to_dict()}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskCreateParams":
        task_payload = payload.get("task")
        if not isinstance(task_payload, dict):
            raise ValueError("task.create params must include a task object")
        return cls(task=TaskCreateRequest.from_dict(task_payload))


@dataclass(slots=True)
class TaskCreateResult:
    task_id: str
    run_id: str
    status: str
    accepted_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TaskSnapshot:
    task_id: str
    run_id: str
    status: TaskStatus
    objective: str
    created_at: str
    updated_at: str
    scope: list[str] | None = None
    success_criteria: list[str] | None = None
    constraints: list[str] | None = None
    workspace_roots: list[str] | None = None
    current_phase: str | None = None
    latest_summary: str | None = None
    awaiting_approval: bool | None = None
    active_subagent: str | None = None
    artifact_count: int | None = None
    last_event_at: str | None = None
    failure: FailureInfo | None = None
    links: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        if self.failure is not None:
            payload["failure"] = self.failure.to_dict()
        return _strip_none(payload)


@dataclass(slots=True)
class TaskGetParams:
    task_id: str
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskGetParams":
        task_id = str(payload.get("task_id", "")).strip()
        if not task_id:
            raise ValueError("task.get requires task_id")
        run_id = payload.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("task.get run_id must be a string when provided")
        return cls(task_id=task_id, run_id=run_id)


@dataclass(slots=True)
class TaskGetResult:
    task: TaskSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {"task": self.task.to_dict()}


@dataclass(slots=True)
class ArtifactReference:
    artifact_id: str
    task_id: str
    run_id: str
    logical_path: str
    content_type: str
    created_at: str
    persistence_class: str
    source_role: str | None = None
    source_tool: str | None = None
    byte_size: int | None = None
    display_name: str | None = None
    summary: str | None = None
    downloadable: bool | None = None
    hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))


@dataclass(slots=True)
class TaskArtifactsListParams:
    task_id: str
    run_id: str | None = None
    persistence_class: str | None = None
    content_type_prefix: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskArtifactsListParams":
        task_id = str(payload.get("task_id", "")).strip()
        if not task_id:
            raise ValueError("task.artifacts.list requires task_id")
        run_id = payload.get("run_id")
        persistence_class = payload.get("persistence_class")
        content_type_prefix = payload.get("content_type_prefix")
        for name, value in (
            ("run_id", run_id),
            ("persistence_class", persistence_class),
            ("content_type_prefix", content_type_prefix),
        ):
            if value is not None and not isinstance(value, str):
                raise ValueError(f"task.artifacts.list {name} must be a string when provided")
        return cls(
            task_id=task_id,
            run_id=run_id,
            persistence_class=persistence_class,
            content_type_prefix=content_type_prefix,
        )


@dataclass(slots=True)
class TaskArtifactsListResult:
    artifacts: list[ArtifactReference]

    def to_dict(self) -> dict[str, Any]:
        return {"artifacts": [artifact.to_dict() for artifact in self.artifacts]}


@dataclass(slots=True)
class TaskLogsStreamParams:
    task_id: str
    run_id: str | None = None
    from_event_id: str | None = None
    include_history: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskLogsStreamParams":
        task_id = str(payload.get("task_id", "")).strip()
        if not task_id:
            raise ValueError("task.logs.stream requires task_id")
        run_id = payload.get("run_id")
        from_event_id = payload.get("from_event_id")
        include_history = payload.get("include_history", False)
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("task.logs.stream run_id must be a string when provided")
        if from_event_id is not None and not isinstance(from_event_id, str):
            raise ValueError("task.logs.stream from_event_id must be a string when provided")
        if not isinstance(include_history, bool):
            raise ValueError("task.logs.stream include_history must be a boolean")
        return cls(
            task_id=task_id,
            run_id=run_id,
            from_event_id=from_event_id,
            include_history=include_history,
        )


@dataclass(slots=True)
class TaskLogsStreamResult:
    task_id: str
    run_id: str
    stream_open: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EventEnvelope:
    event_id: str
    event_type: str
    timestamp: str
    correlation_id: str | None
    task_id: str | None
    run_id: str | None
    source: EventSource
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source"] = self.source.to_dict()
        return payload


@dataclass(slots=True)
class RuntimeEvent:
    event: EventEnvelope
    type: str = "runtime.event"
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "protocol_version": self.protocol_version,
            "event": self.event.to_dict(),
        }


@dataclass(slots=True)
class RuntimeHealthResult:
    protocol_version: str
    runtime_name: str
    runtime_version: str
    status: str
    transport: str
    correlation_id: str | None
    identity: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
