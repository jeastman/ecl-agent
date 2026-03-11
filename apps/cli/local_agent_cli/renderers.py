from __future__ import annotations

import json
from typing import Any


def render_health(result: dict[str, Any], correlation_id: str | None) -> list[str]:
    return [
        (
            f"runtime={result['runtime_name']} version={result['runtime_version']} "
            f"status={result['status']} correlation_id={correlation_id}"
        ),
        (
            f"identity={result['identity']['path']} "
            f"hash={result['identity']['sha256'][:12]} transport={result['transport']} "
            f"protocol={result['protocol_version']}"
        ),
    ]


def render_task_created(result: dict[str, Any], correlation_id: str | None) -> list[str]:
    return [
        (
            f"task_id={result['task_id']} run_id={result['run_id']} status={result['status']} "
            f"correlation_id={correlation_id}"
        ),
        f"accepted_at={result['accepted_at']}",
        f"hint=agent logs {result['task_id']}",
    ]


def render_task_snapshot(task: dict[str, Any]) -> list[str]:
    lines = [
        f"task_id={task['task_id']}",
        f"run_id={task['run_id']}",
        f"status={task['status']}",
        f"objective={task['objective']}",
    ]
    optional_fields = (
        ("current_phase", "current_phase"),
        ("latest_summary", "latest_summary"),
        ("active_subagent", "active_subagent"),
        ("artifact_count", "artifact_count"),
        ("last_event_at", "last_event_at"),
    )
    for label, key in optional_fields:
        if task.get(key) is not None:
            lines.append(f"{label}={task[key]}")
    failure = task.get("failure")
    if isinstance(failure, dict) and failure.get("message"):
        lines.append(f"failure={failure['message']}")
    return lines


def render_event_timeline(event_payloads: list[dict[str, Any]]) -> list[str]:
    return [format_event(event_payload["event"]) for event_payload in event_payloads]


def format_event(event: dict[str, Any]) -> str:
    event_type = str(event["event_type"])
    payload = event.get("payload", {})
    message = _format_event_message(event_type, payload)
    return f"[{event_type}] {message}"


def _format_event_message(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "task.created":
        return f"objective={payload.get('objective', '<unknown>')}"
    if event_type == "task.started":
        return "execution started"
    if event_type == "plan.updated":
        return str(payload.get("summary") or payload.get("plan") or "plan updated")
    if event_type == "subagent.started":
        role = payload.get("role") or "primary"
        name = payload.get("name") or "primary-agent"
        return f"{role} ({name})"
    if event_type == "tool.called":
        tool = payload.get("tool") or "unknown-tool"
        arguments = payload.get("arguments")
        if arguments:
            return f"{tool} {json.dumps(arguments, sort_keys=True)}"
        return str(tool)
    if event_type == "artifact.created":
        artifact = payload.get("artifact", {})
        return str(artifact.get("logical_path") or "<unknown-artifact>")
    if event_type == "task.completed":
        return str(payload.get("summary") or "success")
    if event_type == "task.failed":
        return str(payload.get("error") or payload.get("summary") or "failed")
    if payload.get("summary"):
        return str(payload["summary"])
    return json.dumps(payload, sort_keys=True)


def render_artifacts(artifacts: list[dict[str, Any]]) -> list[str]:
    if not artifacts:
        return ["no_artifacts=true"]
    lines: list[str] = []
    for artifact in artifacts:
        line = (
            f"artifact_id={artifact['artifact_id']} logical_path={artifact['logical_path']} "
            f"content_type={artifact['content_type']} "
            f"persistence_class={artifact['persistence_class']}"
        )
        if artifact.get("display_name"):
            line += f" display_name={artifact['display_name']}"
        lines.append(line)
    return lines
