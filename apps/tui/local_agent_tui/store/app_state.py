from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Literal, TypedDict


class ConnectionMessage(TypedDict, total=False):
    kind: Literal["connection"]
    status: str
    error: str | None


class RpcMessage(TypedDict):
    kind: Literal["rpc"]
    name: str
    payload: dict[str, Any]


class EventMessage(TypedDict):
    kind: Literal["event"]
    payload: dict[str, Any]


class UiMessage(TypedDict, total=False):
    kind: Literal["ui"]
    active_screen: str
    focused_pane: str
    selected_task_id: str | None
    selected_approval_id: str | None
    selected_artifact_id: str | None
    artifact_browser_selected_id: str | None
    artifact_group_by: str
    artifact_browser_origin_screen: str
    markdown_viewer_artifact_id: str | None
    artifact_preview_artifact_id: str
    artifact_preview_status: str
    artifact_preview_error: str | None
    approval_feedback: str | None
    selected_memory_group_id: str | None
    selected_memory_entry_id: str | None
    memory_request_context_key: str | None
    memory_request_status: str
    memory_request_error: str | None
    memory_origin_screen: str


RuntimeMessage = ConnectionMessage | RpcMessage | EventMessage | UiMessage


@dataclass(frozen=True, slots=True)
class TaskEventRecord:
    timestamp: str
    event_type: str
    task_id: str
    run_id: str
    source_kind: str
    source_name: str | None
    summary: str
    payload: dict[str, Any]
    severity: str


@dataclass(slots=True)
class AppState:
    connection_status: str = "disconnected"
    last_error: str | None = None
    runtime_health: dict[str, Any] = field(default_factory=dict)
    task_index: list[str] = field(default_factory=list)
    task_snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    run_event_buffers: dict[tuple[str, str], list[TaskEventRecord]] = field(default_factory=dict)
    approvals_by_task: dict[tuple[str, str], list[dict[str, Any]]] = field(default_factory=dict)
    artifacts_by_task: dict[tuple[str, str], list[dict[str, Any]]] = field(default_factory=dict)
    selected_artifact_id_by_task: dict[tuple[str, str], str | None] = field(default_factory=dict)
    selected_task_id: str | None = None
    selected_approval_id: str | None = None
    active_screen: str = "dashboard"
    focused_pane: str = "tasks"
    approval_feedback: str | None = None
    artifact_group_by: str = "task"
    artifact_browser_selected_id: str | None = None
    artifact_browser_origin_screen: str = "dashboard"
    artifact_preview_status_by_artifact: dict[str, str] = field(default_factory=dict)
    artifact_preview_error_by_artifact: dict[str, str | None] = field(default_factory=dict)
    artifact_preview_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    markdown_viewer_artifact_id: str | None = None
    memory_entries_by_context: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    selected_memory_group_id: str | None = None
    selected_memory_entry_id: str | None = None
    memory_request_context_key: str | None = None
    memory_request_status: str = "idle"
    memory_request_error: str | None = None
    memory_origin_screen: str = "dashboard"


class AppStateStore:
    def __init__(self) -> None:
        self._state = AppState()
        self._lock = RLock()

    def dispatch(self, message: RuntimeMessage) -> AppState:
        from .reducers import reduce_app_state

        with self._lock:
            self._state = reduce_app_state(self._state, message)
            return self._state

    def snapshot(self) -> AppState:
        with self._lock:
            return self._state
