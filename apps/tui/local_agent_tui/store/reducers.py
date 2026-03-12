from __future__ import annotations

from dataclasses import replace
from typing import Any

from packages.task_model.local_agent_task_model.models import FailureInfo

from .app_state import AppState, RuntimeMessage, TaskEventRecord

_MAX_EVENT_BUFFER = 250


def reduce_app_state(state: AppState, message: RuntimeMessage) -> AppState:
    if message["kind"] == "connection":
        return replace(
            state,
            connection_status=str(message["status"]),
            last_error=_normalize_error(message.get("error")),
        )

    if message["kind"] == "ui":
        return _reduce_ui_message(state, message)

    if message["kind"] == "rpc":
        return _reduce_rpc_result(state, str(message["name"]), message["payload"])

    if message["kind"] == "event":
        return _reduce_runtime_event(state, message["payload"])

    return state


def _reduce_ui_message(state: AppState, message: RuntimeMessage) -> AppState:
    assert message["kind"] == "ui"
    state_next = replace(
        state,
        active_screen=str(message.get("active_screen", state.active_screen)),
        focused_pane=str(message.get("focused_pane", state.focused_pane)),
        selected_task_id=message.get("selected_task_id", state.selected_task_id),
        selected_approval_id=message.get("selected_approval_id", state.selected_approval_id),
        approval_feedback=message.get("approval_feedback", state.approval_feedback),
        artifact_group_by=str(message.get("artifact_group_by", state.artifact_group_by)),
        artifact_browser_origin_screen=str(
            message.get("artifact_browser_origin_screen", state.artifact_browser_origin_screen)
        ),
        markdown_viewer_artifact_id=message.get(
            "markdown_viewer_artifact_id", state.markdown_viewer_artifact_id
        ),
        artifact_browser_selected_id=message.get(
            "artifact_browser_selected_id", state.artifact_browser_selected_id
        ),
        selected_memory_group_id=message.get(
            "selected_memory_group_id", state.selected_memory_group_id
        ),
        selected_memory_entry_id=message.get(
            "selected_memory_entry_id", state.selected_memory_entry_id
        ),
        memory_request_context_key=message.get(
            "memory_request_context_key", state.memory_request_context_key
        ),
        memory_request_status=str(
            message.get("memory_request_status", state.memory_request_status)
        ),
        memory_request_error=_normalize_error(
            message.get("memory_request_error", state.memory_request_error)
        ),
        memory_origin_screen=str(message.get("memory_origin_screen", state.memory_origin_screen)),
    )
    selected_artifact_id = message.get("selected_artifact_id")
    if isinstance(selected_artifact_id, str):
        task_key = _selected_task_key(state_next)
        if task_key is None:
            return state_next
        selected_artifacts = dict(state_next.selected_artifact_id_by_task)
        selected_artifacts[task_key] = selected_artifact_id
        state_next = replace(state_next, selected_artifact_id_by_task=selected_artifacts)

    preview_status = message.get("artifact_preview_status")
    preview_artifact_id = message.get("artifact_preview_artifact_id")
    if not isinstance(preview_artifact_id, str) or not isinstance(preview_status, str):
        return state_next
    next_status = dict(state_next.artifact_preview_status_by_artifact)
    next_status[preview_artifact_id] = preview_status
    next_errors = dict(state_next.artifact_preview_error_by_artifact)
    next_errors[preview_artifact_id] = _normalize_error(message.get("artifact_preview_error"))
    return replace(
        state_next,
        artifact_preview_status_by_artifact=next_status,
        artifact_preview_error_by_artifact=next_errors,
    )


def _reduce_rpc_result(state: AppState, name: str, payload: dict[str, Any]) -> AppState:
    if name == "runtime.health":
        result = dict(payload.get("result", {}))
        return replace(
            state,
            runtime_health=result,
            connection_status="connected",
            last_error=None,
        )

    if name in {"task.get", "task.resume", "task.approve"}:
        task = _merge_task_snapshot(
            state.task_snapshots.get(str(payload["result"]["task"]["task_id"])),
            dict(payload["result"]["task"]),
        )
        next_state = _replace_task(state, task)
        return _ensure_task_buffers(
            next_state, task_id=str(task["task_id"]), run_id=str(task["run_id"])
        )

    if name == "task.list":
        result = dict(payload.get("result", {}))
        next_state = state
        tasks = list(result.get("tasks", []))
        for task in reversed(tasks):
            merged_task = _merge_task_snapshot(
                next_state.task_snapshots.get(str(task["task_id"])),
                dict(task),
            )
            next_state = _replace_task(next_state, merged_task, preserve_selection=True)
            next_state = _ensure_task_buffers(
                next_state,
                task_id=str(merged_task["task_id"]),
                run_id=str(merged_task.get("run_id", "")),
            )
        if state.selected_task_id is None and tasks:
            next_state = replace(next_state, selected_task_id=str(tasks[0]["task_id"]))
        return next_state

    if name == "task.approvals.list":
        result = dict(payload["result"])
        approvals = list(result.get("approvals", []))
        task_id, run_id = _extract_task_run_from_entries(approvals)
        approvals_by_task = dict(state.approvals_by_task)
        if task_id is not None and run_id is not None:
            approvals_by_task[(task_id, run_id)] = _dedupe_entries(
                approvals, key_name="approval_id"
            )
        selected_approval_id = _resolved_selected_approval_id(
            approvals_by_task,
            current_id=state.selected_approval_id,
        )
        return replace(
            state,
            approvals_by_task=approvals_by_task,
            selected_approval_id=selected_approval_id,
        )

    if name == "task.artifacts.list":
        result = dict(payload["result"])
        artifacts = list(result.get("artifacts", []))
        task_id, run_id = _extract_task_run_from_entries(artifacts)
        artifacts_by_task = dict(state.artifacts_by_task)
        selected_artifact_id_by_task = dict(state.selected_artifact_id_by_task)
        if task_id is not None and run_id is not None:
            task_key = (task_id, run_id)
            artifacts_by_task[task_key] = _dedupe_entries(artifacts, key_name="artifact_id")
            selected_artifact_id_by_task[task_key] = _default_selected_artifact_id(
                selected_artifact_id_by_task.get(task_key),
                artifacts_by_task[task_key],
            )
        return replace(
            state,
            artifacts_by_task=artifacts_by_task,
            selected_artifact_id_by_task=selected_artifact_id_by_task,
        )

    if name == "task.artifact.get":
        result = dict(payload["result"])
        artifact = dict(result.get("artifact", {}))
        artifact_id = str(artifact.get("artifact_id", ""))
        if not artifact_id:
            return state
        preview_cache = dict(state.artifact_preview_cache)
        preview_cache[artifact_id] = result
        preview_status = dict(state.artifact_preview_status_by_artifact)
        preview_status[artifact_id] = "loaded"
        preview_errors = dict(state.artifact_preview_error_by_artifact)
        preview_errors[artifact_id] = None
        return replace(
            state,
            artifact_preview_cache=preview_cache,
            artifact_preview_status_by_artifact=preview_status,
            artifact_preview_error_by_artifact=preview_errors,
        )

    if name == "memory.inspect":
        result = dict(payload.get("result", {}))
        context_key = _memory_context_key_from_payload(payload)
        memory_entries_by_context = dict(state.memory_entries_by_context)
        memory_entries_by_context[context_key] = [
            dict(entry) for entry in list(result.get("entries", [])) if isinstance(entry, dict)
        ]
        return replace(
            state,
            memory_entries_by_context=memory_entries_by_context,
            memory_request_context_key=context_key,
            memory_request_status="loaded",
            memory_request_error=None,
        )

    if name == "task.logs.stream":
        result = dict(payload["result"])
        selected_task_id = str(result.get("task_id", state.selected_task_id or ""))
        selected_run_id = str(result.get("run_id", ""))
        next_state = replace(
            state,
            selected_task_id=selected_task_id or state.selected_task_id,
            connection_status="connected",
        )
        if selected_task_id and selected_run_id:
            next_state = _ensure_task_buffers(
                next_state, task_id=selected_task_id, run_id=selected_run_id
            )
        return next_state

    return state


def _reduce_runtime_event(state: AppState, payload: dict[str, Any]) -> AppState:
    envelope = dict(payload["event"])
    task_id = envelope.get("task_id")
    run_id = envelope.get("run_id")
    if not isinstance(task_id, str) or not isinstance(run_id, str):
        return state

    next_state = _ensure_task_buffers(state, task_id=task_id, run_id=run_id)
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
    if "phase" in event_payload:
        snapshot["current_phase"] = event_payload["phase"]

    if event_type == "task.started":
        snapshot["status"] = "executing"
    elif event_type == "task.paused":
        snapshot["status"] = "paused"
    elif event_type == "task.resumed":
        snapshot["status"] = "executing"
        snapshot["awaiting_approval"] = False
        snapshot["pending_approval_id"] = None
    elif event_type == "task.completed":
        snapshot["status"] = "completed"
        snapshot["awaiting_approval"] = False
        snapshot["pending_approval_id"] = None
        snapshot["active_subagent"] = None
    elif event_type == "task.failed":
        snapshot["status"] = "failed"
        snapshot["awaiting_approval"] = False
        snapshot["pending_approval_id"] = None
        snapshot["active_subagent"] = None
        snapshot["failure"] = FailureInfo(
            message=str(event_payload.get("error", "failed"))
        ).to_dict()
    elif event_type == "approval.requested":
        snapshot["awaiting_approval"] = True
        snapshot["status"] = "awaiting_approval"
        snapshot["pending_approval_id"] = event_payload.get("approval", {}).get("approval_id")
        approvals = list(next_state.approvals_by_task.get((task_id, run_id), []))
        approvals.append(dict(event_payload["approval"]))
        approvals_by_task = dict(next_state.approvals_by_task)
        approvals_by_task[(task_id, run_id)] = _dedupe_entries(approvals, key_name="approval_id")
        next_state = replace(
            next_state,
            approvals_by_task=approvals_by_task,
            selected_approval_id=next_state.selected_approval_id
            or approvals_by_task[(task_id, run_id)][-1].get("approval_id"),
        )
    elif event_type == "artifact.created":
        artifacts = list(next_state.artifacts_by_task.get((task_id, run_id), []))
        artifacts.append(dict(event_payload["artifact"]))
        artifacts_by_task = dict(next_state.artifacts_by_task)
        artifacts_by_task[(task_id, run_id)] = _dedupe_entries(artifacts, key_name="artifact_id")
        selected_artifact_id_by_task = dict(next_state.selected_artifact_id_by_task)
        selected_artifact_id_by_task[(task_id, run_id)] = _default_selected_artifact_id(
            selected_artifact_id_by_task.get((task_id, run_id)),
            artifacts_by_task[(task_id, run_id)],
        )
        snapshot["artifact_count"] = len(artifacts_by_task[(task_id, run_id)])
        next_state = replace(
            next_state,
            artifacts_by_task=artifacts_by_task,
            selected_artifact_id_by_task=selected_artifact_id_by_task,
        )
    elif event_type == "plan.updated":
        if "summary" in event_payload:
            snapshot["latest_summary"] = event_payload["summary"]
        snapshot["current_phase"] = event_payload.get(
            "phase", snapshot.get("current_phase", "planning")
        )
    elif event_type == "subagent.started":
        snapshot["active_subagent"] = event_payload.get("subagentId")
    elif event_type == "subagent.completed":
        snapshot["active_subagent"] = None

    next_state = _append_event_record(
        next_state,
        _build_task_event_record(
            task_id=task_id,
            run_id=run_id,
            timestamp=str(envelope["timestamp"]),
            event_type=event_type,
            payload=event_payload,
            source=dict(envelope.get("source", {})),
        ),
    )
    return _replace_task(next_state, snapshot, preserve_selection=True)


def _replace_task(
    state: AppState, task: dict[str, Any], *, preserve_selection: bool = False
) -> AppState:
    task_id = str(task["task_id"])
    task_snapshots = dict(state.task_snapshots)
    task_snapshots[task_id] = task
    if preserve_selection and task_id in state.task_index:
        task_index = [candidate for candidate in state.task_index if candidate != task_id]
        task_index.insert(0, task_id)
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


def _merge_task_snapshot(
    existing: dict[str, Any] | None, incoming: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(existing or {})
    merged.update(incoming)
    return merged


def _ensure_task_buffers(state: AppState, *, task_id: str, run_id: str) -> AppState:
    task_key = (task_id, run_id)
    run_event_buffers = state.run_event_buffers
    selected_artifact_id_by_task = state.selected_artifact_id_by_task
    if task_key in run_event_buffers and task_key in selected_artifact_id_by_task:
        return state
    next_buffers = dict(run_event_buffers)
    next_buffers.setdefault(task_key, [])
    next_selected = dict(selected_artifact_id_by_task)
    next_selected.setdefault(task_key, None)
    return replace(
        state,
        run_event_buffers=next_buffers,
        selected_artifact_id_by_task=next_selected,
    )


def _append_event_record(state: AppState, record: TaskEventRecord) -> AppState:
    task_key = (record.task_id, record.run_id)
    run_event_buffers = dict(state.run_event_buffers)
    events = list(run_event_buffers.get(task_key, []))
    if not _event_record_exists(events, record):
        events.append(record)
        if len(events) > _MAX_EVENT_BUFFER:
            events = events[-_MAX_EVENT_BUFFER:]
    run_event_buffers[task_key] = events
    return replace(state, run_event_buffers=run_event_buffers)


def _event_record_exists(events: list[TaskEventRecord], record: TaskEventRecord) -> bool:
    return any(
        event.timestamp == record.timestamp
        and event.event_type == record.event_type
        and event.summary == record.summary
        for event in events
    )


def _build_task_event_record(
    *,
    task_id: str,
    run_id: str,
    timestamp: str,
    event_type: str,
    payload: dict[str, Any],
    source: dict[str, Any],
) -> TaskEventRecord:
    return TaskEventRecord(
        timestamp=timestamp,
        event_type=event_type,
        task_id=task_id,
        run_id=run_id,
        source_kind=str(source.get("kind", "runtime")),
        source_name=_source_name(source),
        summary=_event_summary(event_type, payload),
        payload=payload,
        severity=_event_severity(event_type),
    )


def _source_name(source: dict[str, Any]) -> str | None:
    for key in ("name", "role", "component"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _event_summary(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "plan.updated":
        return str(payload.get("summary") or "Plan updated")
    if event_type == "subagent.started":
        return f"Started {payload.get('subagentId', 'subagent')}"
    if event_type == "subagent.completed":
        status = str(payload.get("status", "done"))
        return f"{payload.get('subagentId', 'subagent')} completed ({status})"
    if event_type == "tool.called":
        tool = str(payload.get("tool", "tool"))
        if isinstance(payload.get("path"), str):
            return f"{tool} {payload['path']}"
        if isinstance(payload.get("logical_path"), str):
            return f"{tool} {payload['logical_path']}"
        if isinstance(payload.get("count"), int):
            return f"{tool} ({payload['count']})"
        return tool
    if event_type == "artifact.created":
        artifact = payload.get("artifact", {})
        if isinstance(artifact, dict):
            return str(
                artifact.get("display_name")
                or artifact.get("logical_path")
                or artifact.get("artifact_id")
                or "artifact"
            )
        return "artifact"
    if event_type == "approval.requested":
        approval = payload.get("approval", {})
        if isinstance(approval, dict):
            return str(approval.get("description") or approval.get("type") or "Approval requested")
        return "Approval requested"
    if event_type == "task.failed":
        return str(payload.get("error") or "failed")
    return event_type


def _event_severity(event_type: str) -> str:
    if event_type in {"task.failed", "policy.denied", "skill.install.failed"}:
        return "error"
    if event_type in {"approval.requested", "task.paused"}:
        return "attention"
    if event_type in {"artifact.created", "task.completed", "task.resumed"}:
        return "success"
    return "info"


def _extract_task_run_from_entries(entries: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    if not entries:
        return None, None
    first = entries[0]
    task_id = first.get("task_id")
    run_id = first.get("run_id")
    if not isinstance(task_id, str) or not isinstance(run_id, str):
        return None, None
    return task_id, run_id


def _dedupe_entries(entries: list[dict[str, Any]], *, key_name: str) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    ordered_without_key: list[dict[str, Any]] = []
    for entry in entries:
        key = entry.get(key_name)
        if isinstance(key, str) and key.strip():
            deduped[key] = entry
        else:
            ordered_without_key.append(entry)
    return [*ordered_without_key, *deduped.values()]


def _default_selected_artifact_id(
    current_id: str | None,
    artifacts: list[dict[str, Any]],
) -> str | None:
    artifact_ids = [
        str(artifact["artifact_id"])
        for artifact in artifacts
        if isinstance(artifact.get("artifact_id"), str)
    ]
    if current_id in artifact_ids:
        return current_id
    return artifact_ids[0] if artifact_ids else None


def _resolved_selected_approval_id(
    approvals_by_task: dict[tuple[str, str], list[dict[str, Any]]],
    *,
    current_id: str | None,
) -> str | None:
    pending_entries: list[dict[str, Any]] = []
    for entries in approvals_by_task.values():
        for approval in entries:
            status = str(approval.get("status", "pending"))
            if status in {"pending", "waiting"}:
                pending_entries.append(approval)
    pending_entries.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    pending_ids = [
        str(item["approval_id"])
        for item in pending_entries
        if isinstance(item.get("approval_id"), str)
    ]
    if current_id in pending_ids:
        return current_id
    return pending_ids[0] if pending_ids else None


def _selected_task_key(state: AppState) -> tuple[str, str] | None:
    if state.selected_task_id is None:
        return None
    task = state.task_snapshots.get(state.selected_task_id)
    if task is None:
        return None
    run_id = task.get("run_id")
    if not isinstance(run_id, str):
        return None
    return (state.selected_task_id, run_id)


def _normalize_error(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _memory_context_key_from_payload(payload: dict[str, Any]) -> str:
    context = payload.get("context")
    if not isinstance(context, dict):
        return "global"
    task_id = context.get("task_id")
    run_id = context.get("run_id")
    if isinstance(task_id, str) and task_id.strip():
        if isinstance(run_id, str) and run_id.strip():
            return f"{task_id}:{run_id}"
        return task_id
    return "global"
