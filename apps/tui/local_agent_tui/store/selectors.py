from __future__ import annotations

from .app_state import AppState


def connection_label(state: AppState) -> str:
    if state.last_error:
        return f"{state.connection_status} ({state.last_error})"
    return state.connection_status


def runtime_health_label(state: AppState) -> str:
    if not state.runtime_health:
        return "unknown"
    return str(state.runtime_health.get("status", "unknown"))


def task_count(state: AppState) -> int:
    return len(state.task_index)


def approval_count(state: AppState) -> int:
    return sum(
        1
        for approvals in state.approvals_by_task.values()
        for approval in approvals
        if approval.get("status", "pending") in {"pending", "waiting"}
    )


def artifact_count(state: AppState) -> int:
    return sum(len(artifacts) for artifacts in state.artifacts_by_task.values())
