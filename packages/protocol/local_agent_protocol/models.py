from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

from packages.task_model.local_agent_task_model.models import FailureInfo, TaskStatus, TodoItem

PROTOCOL_VERSION = "1.0.0"

METHOD_RUNTIME_HEALTH = "runtime.health"
METHOD_TASK_CREATE = "task.create"
METHOD_TASK_LIST = "task.list"
METHOD_TASK_GET = "task.get"
METHOD_TASK_APPROVE = "task.approve"
METHOD_TASK_APPROVALS_LIST = "task.approvals.list"
METHOD_TASK_DIAGNOSTICS_LIST = "task.diagnostics.list"
METHOD_TASK_REPLY = "task.reply"
METHOD_TASK_RESUME = "task.resume"
METHOD_TASK_COMPACT = "task.compact"
METHOD_TASK_LOGS_STREAM = "task.logs.stream"
METHOD_TASK_ARTIFACTS_LIST = "task.artifacts.list"
METHOD_TASK_ARTIFACT_GET = "task.artifact.get"
METHOD_SKILL_INSTALL = "skill.install"
METHOD_MEMORY_INSPECT = "memory.inspect"
METHOD_CONFIG_GET = "config.get"


def utc_now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _validate_workspace_roots(workspace_roots: list[str]) -> list[str]:
    validated: list[str] = []
    for item in workspace_roots:
        raw = item.strip()
        if raw.startswith("~") or raw.startswith("$"):
            raise ValueError("task.workspace_roots must use sandbox virtual paths")
        if len(raw) >= 3 and raw[1] == ":" and raw[2] in {"\\", "/"}:
            raise ValueError("task.workspace_roots must use sandbox virtual paths")
        candidate = PurePosixPath(raw)
        if not candidate.is_absolute():
            raise ValueError("task.workspace_roots must be absolute virtual paths")
        for part in candidate.parts:
            if part in {"", "."}:
                continue
            if part == "..":
                raise ValueError("task.workspace_roots cannot traverse outside the sandbox")
        if raw == "/" or not (raw == "/workspace" or raw.startswith("/workspace/")):
            raise ValueError("task.workspace_roots must be under /workspace")
        validated.append(candidate.as_posix())
    return validated


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
            workspace_roots=_validate_workspace_roots(workspace_roots),
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
    todos: list[TodoItem] | None = None
    awaiting_approval: bool | None = None
    pending_approval_id: str | None = None
    is_resumable: bool | None = None
    pause_reason: str | None = None
    checkpoint_thread_id: str | None = None
    latest_checkpoint_id: str | None = None
    is_compacted: bool | None = None
    latest_compaction_id: str | None = None
    latest_compaction_trigger: str | None = None
    active_subagent: str | None = None
    artifact_count: int | None = None
    recoverable_rejection_count: int | None = None
    last_event_at: str | None = None
    failure: FailureInfo | None = None
    last_recoverable_rejection: FailureInfo | None = None
    links: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        if self.failure is not None:
            payload["failure"] = self.failure.to_dict()
        if self.last_recoverable_rejection is not None:
            payload["last_recoverable_rejection"] = self.last_recoverable_rejection.to_dict()
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
class TaskListParams:
    limit: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskListParams":
        limit = payload.get("limit")
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ValueError("task.list limit must be a positive integer when provided")
        return cls(limit=limit)


@dataclass(slots=True)
class TaskListResult:
    tasks: list[TaskSnapshot]
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks": [task.to_dict() for task in self.tasks],
            "count": self.count,
        }


@dataclass(slots=True)
class TaskGetResult:
    task: TaskSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {"task": self.task.to_dict()}


@dataclass(slots=True)
class TaskResumeParams:
    task_id: str
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskResumeParams":
        task_id = str(payload.get("task_id", "")).strip()
        if not task_id:
            raise ValueError("task.resume requires task_id")
        run_id = payload.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("task.resume run_id must be a string when provided")
        return cls(task_id=task_id, run_id=run_id)


@dataclass(slots=True)
class TaskResumeResult:
    task: TaskSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {"task": self.task.to_dict()}


@dataclass(slots=True)
class TaskCompactParams:
    task_id: str
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskCompactParams":
        task_id = str(payload.get("task_id", "")).strip()
        if not task_id:
            raise ValueError("task.compact requires task_id")
        run_id = payload.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("task.compact run_id must be a string when provided")
        return cls(task_id=task_id, run_id=run_id)


@dataclass(slots=True)
class TaskCompactResult:
    task: TaskSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {"task": self.task.to_dict()}


@dataclass(slots=True)
class TaskReplyParams:
    task_id: str
    message: str
    run_id: str | None = None
    background: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "task_id": self.task_id,
                "run_id": self.run_id,
                "message": self.message,
                "background": self.background if self.background else None,
            }
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskReplyParams":
        task_id = str(payload.get("task_id", "")).strip()
        if not task_id:
            raise ValueError("task.reply requires task_id")
        run_id = payload.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("task.reply run_id must be a string when provided")
        message = str(payload.get("message", "")).strip()
        if not message:
            raise ValueError("task.reply requires message")
        background = payload.get("background", False)
        if not isinstance(background, bool):
            raise ValueError("task.reply background must be a boolean when provided")
        return cls(task_id=task_id, run_id=run_id, message=message, background=background)


@dataclass(slots=True)
class TaskReplyResult:
    task: TaskSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {"task": self.task.to_dict()}


@dataclass(slots=True)
class ApprovalDecisionPayload:
    approval_id: str
    decision: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ApprovalDecisionPayload":
        approval_id = str(payload.get("approval_id", "")).strip()
        decision = str(payload.get("decision", "")).strip()
        if not approval_id:
            raise ValueError("task.approve requires approval.approval_id")
        if decision not in {"approved", "rejected"}:
            raise ValueError("task.approve approval.decision must be approved or rejected")
        return cls(approval_id=approval_id, decision=decision)


@dataclass(slots=True)
class TaskApproveParams:
    task_id: str | None
    approval: ApprovalDecisionPayload
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = _strip_none(asdict(self))
        payload["approval"] = self.approval.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskApproveParams":
        task_id_value = payload.get("task_id")
        if task_id_value is not None and not isinstance(task_id_value, str):
            raise ValueError("task.approve task_id must be a string when provided")
        task_id = str(task_id_value).strip() if isinstance(task_id_value, str) else None
        run_id = payload.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("task.approve run_id must be a string when provided")
        approval_payload = payload.get("approval")
        if not isinstance(approval_payload, dict):
            raise ValueError("task.approve requires approval")
        return cls(
            task_id=task_id,
            run_id=run_id,
            approval=ApprovalDecisionPayload.from_dict(approval_payload),
        )


@dataclass(slots=True)
class TaskApproveResult:
    approval_id: str
    accepted: bool
    status: str
    task: TaskSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "accepted": self.accepted,
            "status": self.status,
            "task": self.task.to_dict(),
        }


@dataclass(slots=True)
class TaskApprovalsListParams:
    task_id: str
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskApprovalsListParams":
        task_id = str(payload.get("task_id", "")).strip()
        if not task_id:
            raise ValueError("task.approvals.list requires task_id")
        run_id = payload.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("task.approvals.list run_id must be a string when provided")
        return cls(task_id=task_id, run_id=run_id)


@dataclass(slots=True)
class ApprovalEntry:
    approval_id: str
    task_id: str
    run_id: str
    status: str
    type: str
    scope: dict[str, Any]
    scope_summary: str
    description: str
    created_at: str
    decision: str | None = None
    decided_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))


@dataclass(slots=True)
class TaskApprovalsListResult:
    approvals: list[ApprovalEntry]
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "approvals": [approval.to_dict() for approval in self.approvals],
            "count": self.count,
        }


@dataclass(slots=True)
class TaskDiagnosticsListParams:
    task_id: str
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskDiagnosticsListParams":
        task_id = str(payload.get("task_id", "")).strip()
        if not task_id:
            raise ValueError("task.diagnostics.list requires task_id")
        run_id = payload.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("task.diagnostics.list run_id must be a string when provided")
        return cls(task_id=task_id, run_id=run_id)


@dataclass(slots=True)
class DiagnosticEntry:
    diagnostic_id: str
    task_id: str
    run_id: str
    kind: str
    message: str
    created_at: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TaskDiagnosticsListResult:
    diagnostics: list[DiagnosticEntry]
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            "count": self.count,
        }


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
class ArtifactPreviewPayload:
    kind: str
    text: str | None = None
    encoding: str | None = None
    truncated: bool | None = None
    message: str | None = None

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
class TaskArtifactGetParams:
    task_id: str
    artifact_id: str
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskArtifactGetParams":
        task_id = str(payload.get("task_id", "")).strip()
        artifact_id = str(payload.get("artifact_id", "")).strip()
        if not task_id:
            raise ValueError("task.artifact.get requires task_id")
        if not artifact_id:
            raise ValueError("task.artifact.get requires artifact_id")
        run_id = payload.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("task.artifact.get run_id must be a string when provided")
        return cls(task_id=task_id, artifact_id=artifact_id, run_id=run_id)


@dataclass(slots=True)
class TaskArtifactGetResult:
    artifact: ArtifactReference
    preview: ArtifactPreviewPayload
    external_open_supported: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact": self.artifact.to_dict(),
            "preview": self.preview.to_dict(),
            "external_open_supported": self.external_open_supported,
        }


@dataclass(slots=True)
class SkillInstallValidation:
    status: str
    findings: list[dict[str, Any]]
    has_scripts: bool
    total_bytes: int
    file_count: int
    skill_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SkillInstallValidation":
        status = str(payload.get("status", "")).strip()
        if status not in {"pass", "pass_with_warnings", "fail"}:
            raise ValueError(
                "skill.install validation.status must be pass, pass_with_warnings, or fail"
            )
        findings = payload.get("findings", [])
        if not isinstance(findings, list) or not all(isinstance(item, dict) for item in findings):
            raise ValueError("skill.install validation.findings must be a list of objects")
        has_scripts = payload.get("has_scripts", False)
        total_bytes = payload.get("total_bytes", 0)
        file_count = payload.get("file_count", 0)
        skill_id = payload.get("skill_id")
        if not isinstance(has_scripts, bool):
            raise ValueError("skill.install validation.has_scripts must be a boolean")
        if not isinstance(total_bytes, int):
            raise ValueError("skill.install validation.total_bytes must be an integer")
        if not isinstance(file_count, int):
            raise ValueError("skill.install validation.file_count must be an integer")
        if skill_id is not None and not isinstance(skill_id, str):
            raise ValueError("skill.install validation.skill_id must be a string when provided")
        return cls(
            status=status,
            findings=findings,
            has_scripts=has_scripts,
            total_bytes=total_bytes,
            file_count=file_count,
            skill_id=skill_id,
        )


@dataclass(slots=True)
class SkillInstallParams:
    task_id: str
    source_path: str
    target_scope: str
    target_role: str | None = None
    install_mode: str = "fail_if_exists"
    reason: str = ""
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SkillInstallParams":
        task_id = str(payload.get("task_id", "")).strip()
        source_path = str(payload.get("source_path", "")).strip()
        target_scope = str(payload.get("target_scope", "")).strip()
        target_role = payload.get("target_role")
        install_mode = str(payload.get("install_mode", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        run_id = payload.get("run_id")
        if not task_id:
            raise ValueError("skill.install requires task_id")
        if not source_path:
            raise ValueError("skill.install requires source_path")
        if target_scope not in {"primary_agent", "subagent"}:
            raise ValueError("skill.install target_scope must be primary_agent or subagent")
        if target_role is not None and not isinstance(target_role, str):
            raise ValueError("skill.install target_role must be a string when provided")
        if target_scope == "subagent" and (
            not isinstance(target_role, str) or not target_role.strip()
        ):
            raise ValueError("skill.install target_role is required for subagent installs")
        if install_mode not in {"fail_if_exists", "replace"}:
            raise ValueError("skill.install install_mode must be fail_if_exists or replace")
        if not reason:
            raise ValueError("skill.install requires reason")
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("skill.install run_id must be a string when provided")
        return cls(
            task_id=task_id,
            run_id=run_id,
            source_path=source_path,
            target_scope=target_scope,
            target_role=target_role.strip() if isinstance(target_role, str) else None,
            install_mode=install_mode,
            reason=reason,
        )


@dataclass(slots=True)
class SkillInstallResult:
    status: str
    target_path: str
    validation: SkillInstallValidation
    approval_required: bool
    summary: str
    approval_id: str | None = None
    artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "target_path": self.target_path,
            "validation": self.validation.to_dict(),
            "approval_required": self.approval_required,
            "summary": self.summary,
            "artifacts": list(self.artifacts),
        }
        if self.approval_id is not None:
            payload["approval_id"] = self.approval_id
        return payload


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
class MemoryInspectEntry:
    memory_id: str
    scope: str
    namespace: str
    content: str
    summary: str
    provenance: dict[str, Any]
    created_at: str
    updated_at: str
    source_run: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))


@dataclass(slots=True)
class MemoryInspectParams:
    task_id: str | None = None
    run_id: str | None = None
    scope: str | None = None
    namespace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryInspectParams":
        task_id = payload.get("task_id")
        run_id = payload.get("run_id")
        scope = payload.get("scope")
        namespace = payload.get("namespace")
        for name, value in (
            ("task_id", task_id),
            ("run_id", run_id),
            ("scope", scope),
            ("namespace", namespace),
        ):
            if value is not None and not isinstance(value, str):
                raise ValueError(f"memory.inspect {name} must be a string when provided")
        if run_id is not None and task_id is None:
            raise ValueError("memory.inspect run_id requires task_id")
        return cls(task_id=task_id, run_id=run_id, scope=scope, namespace=namespace)


@dataclass(slots=True)
class MemoryInspectResult:
    entries: list[MemoryInspectEntry]
    scope: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "scope": self.scope,
            "count": self.count,
        }


@dataclass(slots=True)
class ConfigRedaction:
    path: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ConfigGetResult:
    effective_config: dict[str, Any]
    loaded_profiles: list[str]
    config_sources: list[str]
    redactions: list[ConfigRedaction]

    def to_dict(self) -> dict[str, Any]:
        return {
            "effective_config": self.effective_config,
            "loaded_profiles": list(self.loaded_profiles),
            "config_sources": list(self.config_sources),
            "redactions": [redaction.to_dict() for redaction in self.redactions],
        }


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
    capabilities: dict[str, bool] | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(asdict(self))
