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
        ("pause_reason", "pause_reason"),
        ("checkpoint_thread_id", "checkpoint_thread_id"),
        ("latest_checkpoint_id", "latest_checkpoint_id"),
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
    if event_type == "checkpoint.saved":
        return str(payload.get("checkpoint_id") or "checkpoint recorded")
    if event_type == "task.paused":
        return str(payload.get("reason") or payload.get("summary") or "paused")
    if event_type == "task.resumed":
        return str(payload.get("summary") or "execution resumed")
    if event_type == "recovery.discovered":
        return str(payload.get("summary") or "recovered resumable run")
    if event_type == "plan.updated":
        return str(payload.get("summary") or payload.get("plan") or "plan updated")
    if event_type == "subagent.started":
        subagent_id = payload.get("subagentId") or "primary"
        task_description = payload.get("taskDescription")
        if task_description:
            return f"{subagent_id} taskDescription={task_description}"
        return str(subagent_id)
    if event_type == "subagent.completed":
        subagent_id = payload.get("subagentId") or "primary"
        status = payload.get("status") or "completed"
        duration = payload.get("duration")
        if duration is not None:
            return f"{subagent_id} status={status} duration={duration}"
        return f"{subagent_id} status={status}"
    if event_type == "tool.called":
        tool = payload.get("tool") or "unknown-tool"
        arguments = payload.get("arguments")
        if arguments:
            return f"{tool} {json.dumps(arguments, sort_keys=True)}"
        return str(tool)
    if event_type == "artifact.created":
        artifact = payload.get("artifact", {})
        return str(artifact.get("logical_path") or "<unknown-artifact>")
    if event_type == "skill.install.requested":
        return str(payload.get("source_path") or "skill install requested")
    if event_type == "skill.install.validated":
        validation = payload.get("validation", {})
        return f"status={validation.get('status', 'unknown')}"
    if event_type == "skill.install.approval_requested":
        approval = payload.get("approval", {})
        return str(approval.get("approval_id") or "skill install approval requested")
    if event_type == "skill.install.completed":
        return str(payload.get("target_path") or "skill install completed")
    if event_type == "skill.install.failed":
        return str(payload.get("summary") or "skill install failed")
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


def render_skill_install(result: dict[str, Any]) -> list[str]:
    lines = [
        f"status={result['status']}",
        f"target_path={result['target_path']}",
        f"approval_required={result['approval_required']}",
        f"validation_status={result['validation']['status']}",
        f"summary={result['summary']}",
    ]
    if result.get("approval_id") is not None:
        lines.append(f"approval_id={result['approval_id']}")
    lines.append(f"finding_count={len(result['validation'].get('findings', []))}")
    for artifact in result.get("artifacts", []):
        lines.append(f"artifact={artifact}")
    return lines


def render_approvals(approvals: list[dict[str, Any]]) -> list[str]:
    if not approvals:
        return ["no_approvals=true"]
    lines: list[str] = []
    for approval in approvals:
        line = (
            f"approval_id={approval['approval_id']} status={approval['status']} "
            f"type={approval['type']} scope={approval['scope_summary']}"
        )
        if approval.get("decision") is not None:
            line += f" decision={approval['decision']}"
        if approval.get("decided_at") is not None:
            line += f" decided_at={approval['decided_at']}"
        line += f" created_at={approval['created_at']}"
        if approval.get("description"):
            line += f" description={approval['description']}"
        lines.append(line)
    return lines


def render_diagnostics(diagnostics: list[dict[str, Any]]) -> list[str]:
    if not diagnostics:
        return ["no_diagnostics=true"]
    lines: list[str] = []
    for diagnostic in diagnostics:
        line = (
            f"diagnostic_id={diagnostic['diagnostic_id']} kind={diagnostic['kind']} "
            f"created_at={diagnostic['created_at']} message={diagnostic['message']}"
        )
        details = diagnostic.get("details")
        if details:
            line += f" details={json.dumps(details, sort_keys=True)}"
        lines.append(line)
    return lines


def render_memory(entries: list[dict[str, Any]], *, scope: str, count: int) -> list[str]:
    lines = [f"scope={scope}", f"count={count}"]
    if not entries:
        lines.append("no_memory=true")
        return lines
    for entry in entries:
        line = (
            f"memory_id={entry['memory_id']} scope={entry['scope']} "
            f"namespace={entry['namespace']} summary={entry['summary']}"
        )
        if entry.get("source_run") is not None:
            line += f" source_run={entry['source_run']}"
        line += f" created_at={entry['created_at']} updated_at={entry['updated_at']}"
        provenance = entry.get("provenance")
        if provenance:
            line += f" provenance={json.dumps(provenance, sort_keys=True)}"
        lines.append(line)
    return lines


def render_config(result: dict[str, Any]) -> list[str]:
    lines = [
        f"loaded_profiles={','.join(result.get('loaded_profiles', [])) or '<none>'}",
        f"config_sources={','.join(result.get('config_sources', [])) or '<none>'}",
        f"redaction_count={len(result.get('redactions', []))}",
        json.dumps(result["effective_config"], sort_keys=True),
    ]
    return lines
