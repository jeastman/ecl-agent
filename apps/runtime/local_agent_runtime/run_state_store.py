from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Any
from typing import Protocol

from packages.task_model.local_agent_task_model.models import RunState


class RunStateStore(Protocol):
    def create(self, state: RunState) -> None: ...

    def get(self, task_id: str, run_id: str | None = None) -> RunState: ...

    def update(self, task_id: str, run_id: str, **changes: Any) -> RunState: ...


class InMemoryRunStateStore:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str], RunState] = {}
        self._runs_by_task: dict[str, list[str]] = {}
        self._lock = RLock()

    def create(self, state: RunState) -> None:
        with self._lock:
            key = (state.task_id, state.run_id)
            self._states[key] = state
            self._runs_by_task.setdefault(state.task_id, []).append(state.run_id)

    def get(self, task_id: str, run_id: str | None = None) -> RunState:
        with self._lock:
            resolved_run_id = run_id or self._latest_run_id(task_id)
            key = (task_id, resolved_run_id)
            try:
                return self._states[key]
            except KeyError as exc:
                raise KeyError(f"unknown task/run: {task_id}/{resolved_run_id}") from exc

    def update(self, task_id: str, run_id: str, **changes: Any) -> RunState:
        with self._lock:
            state = self.get(task_id, run_id)
            updated = replace(state, **changes)
            self._states[(task_id, run_id)] = updated
            return updated

    def _latest_run_id(self, task_id: str) -> str:
        runs = self._runs_by_task.get(task_id)
        if not runs:
            raise KeyError(f"unknown task: {task_id}")
        return runs[-1]
