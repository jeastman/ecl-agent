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


RuntimeMessage = ConnectionMessage | RpcMessage | EventMessage | UiMessage


@dataclass(slots=True)
class AppState:
    connection_status: str = "disconnected"
    last_error: str | None = None
    runtime_health: dict[str, Any] = field(default_factory=dict)
    task_index: list[str] = field(default_factory=list)
    task_snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    approvals_by_task: dict[tuple[str, str], list[dict[str, Any]]] = field(default_factory=dict)
    artifacts_by_task: dict[tuple[str, str], list[dict[str, Any]]] = field(default_factory=dict)
    selected_task_id: str | None = None
    selected_approval_id: str | None = None
    active_screen: str = "dashboard"
    focused_pane: str = "tasks"


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
