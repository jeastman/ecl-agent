from __future__ import annotations

from dataclasses import replace
from typing import Any

from packages.task_model.local_agent_task_model.models import FailureInfo

from .app_state import AppState, RuntimeMessage


def reduce_app_state(state: AppState, message: RuntimeMessage) -> AppState:
    if message["kind"] == "connection":
        return replace(
            state,
            connection_status=str(message["status"]),
            last_error=_normalize_error(message.get("error")),
        )

    if message["kind"] == "ui":
        return replace(
            state,
            active_screen=str(message.get("active_screen", state.active_screen)),
            focused_pane=str(message.get("focused_pane", state.focused_pane)),
            selected_task_id=message.get("selected_task_id", state.selected_task_id),
            selected_approval_id=message.get("selected_approval_id", state.selected_approval_id),
        )

    if message["kind"] == "rpc":
        return _reduce_rpc_result(state, str(message["name"]), message["payload"])

    if message["kind"] == "event":
        return _reduce_runtime_event(state, message["payload"])

    return state


def _reduce_rpc_result(state: AppState, name: str, payload: dict[str, Any]) -> AppState:
    if name == "runtime.health":
        result = dict(payload.get("result", {}))
        return replace(
            state,
            runtime_health=result,
            connection_status="connected",
            last_error=None,
        )

    if name in {"task.get", "task.resume"}:
        task = dict(payload["result"]["task"])
        return _replace_task(state, task)

    if name == "task.list":
        result = dict(payload.get("result", {}))
        next_state = state
        tasks = list(result.get("tasks", []))
        for task in reversed(tasks):
            next_state = _replace_task(next_state, dict(task), preserve_selection=True)
        if state.selected_task_id is None and tasks:
            next_state = replace(next_state, selected_task_id=str(tasks[0]["task_id"]))
        return next_state

    if name == "task.approvals.list":
        result = dict(payload["result"])
        task_id = str(result["approvals"][0]["task_id"]) if result["approvals"] else None
        run_id = str(result["approvals"][0]["run_id"]) if result["approvals"] else None
        approvals_by_task = dict(state.approvals_by_task)
        if task_id is not None and run_id is not None:
            approvals_by_task[(task_id, run_id)] = list(result["approvals"])
        selected_approval_id = state.selected_approval_id
        if selected_approval_id is None and result["approvals"]:
            selected_approval_id = result["approvals"][0].get("approval_id")
        return replace(
            state,
            approvals_by_task=approvals_by_task,
            selected_approval_id=selected_approval_id,
        )

    if name == "task.artifacts.list":
        result = dict(payload["result"])
        task_id = str(result["artifacts"][0]["task_id"]) if result["artifacts"] else None
        run_id = str(result["artifacts"][0]["run_id"]) if result["artifacts"] else None
        artifacts_by_task = dict(state.artifacts_by_task)
        if task_id is not None and run_id is not None:
            artifacts_by_task[(task_id, run_id)] = list(result["artifacts"])
        return replace(state, artifacts_by_task=artifacts_by_task)

    if name == "task.logs.stream":
        result = dict(payload["result"])
        selected_task_id = str(result.get("task_id", state.selected_task_id or ""))
        return replace(
            state,
            selected_task_id=selected_task_id or state.selected_task_id,
            connection_status="connected",
        )

    return state


def _reduce_runtime_event(state: AppState, payload: dict[str, Any]) -> AppState:
    envelope = dict(payload["event"])
    task_id = envelope.get("task_id")
    run_id = envelope.get("run_id")
    if not isinstance(task_id, str) or not isinstance(run_id, str):
        return state

    next_state = state
    event_type = str(envelope["event_type"])
    event_payload = dict(envelope.get("payload", {}))
    snapshot = dict(next_state.task_snapshots.get(task_id, {}))
    if not snapshot:
        snapshot = {
            "task_id": task_id,
            "run_id": run_id,
            "status": event_payload.get("status", "created"),
            "objective": event_payload.get("objective", ""),
            "created_at": envelope["timestamp"],
            "updated_at": envelope["timestamp"],
        }

    snapshot["task_id"] = task_id
    snapshot["run_id"] = run_id
    snapshot["updated_at"] = envelope["timestamp"]
    snapshot["last_event_at"] = envelope["timestamp"]

    if "summary" in event_payload:
        snapshot["latest_summary"] = event_payload["summary"]
    if "objective" in event_payload:
        snapshot["objective"] = event_payload["objective"]
    if "status" in event_payload:
        snapshot["status"] = event_payload["status"]

    if event_type == "task.started":
        snapshot["status"] = "executing"
    elif event_type == "task.completed":
        snapshot["status"] = "completed"
    elif event_type == "task.failed":
        snapshot["status"] = "failed"
        snapshot["failure"] = FailureInfo(
            message=str(event_payload.get("error", "failed"))
        ).to_dict()
    elif event_type == "approval.requested":
        snapshot["awaiting_approval"] = True
        snapshot["pending_approval_id"] = event_payload.get("approval", {}).get("approval_id")
        approvals = list(next_state.approvals_by_task.get((task_id, run_id), []))
        approvals.append(dict(event_payload["approval"]))
        approvals_by_task = dict(next_state.approvals_by_task)
        approvals_by_task[(task_id, run_id)] = approvals
        next_state = replace(
            next_state,
            approvals_by_task=approvals_by_task,
            selected_approval_id=next_state.selected_approval_id
            or approvals[-1].get("approval_id"),
        )
    elif event_type == "artifact.created":
        artifacts = list(next_state.artifacts_by_task.get((task_id, run_id), []))
        artifacts.append(dict(event_payload["artifact"]))
        artifacts_by_task = dict(next_state.artifacts_by_task)
        artifacts_by_task[(task_id, run_id)] = artifacts
        snapshot["artifact_count"] = len(artifacts)
        next_state = replace(next_state, artifacts_by_task=artifacts_by_task)

    return _replace_task(next_state, snapshot, preserve_selection=True)


def _replace_task(
    state: AppState, task: dict[str, Any], *, preserve_selection: bool = False
) -> AppState:
    task_id = str(task["task_id"])
    task_snapshots = dict(state.task_snapshots)
    task_snapshots[task_id] = task
    if preserve_selection and task_id in state.task_index:
        task_index = [candidate for candidate in state.task_index if candidate != task_id]
        insert_at = 0
        task_index.insert(insert_at, task_id)
    elif preserve_selection and task_id not in state.task_index:
        task_index = [task_id, *state.task_index]
    else:
        task_index = [
            task_id,
            *[candidate for candidate in state.task_index if candidate != task_id],
        ]
    return replace(
        state,
        task_snapshots=task_snapshots,
        task_index=task_index,
        selected_task_id=state.selected_task_id or task_id,
    )


def _normalize_error(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
