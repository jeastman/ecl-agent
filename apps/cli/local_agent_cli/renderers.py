from __future__ import annotations

import json
from typing import Any

from rich.console import Group, RenderableType
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def render_health(result: dict[str, Any], correlation_id: str | None) -> RenderableType:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Runtime", result["runtime_name"])
    summary.add_row("Version", result["runtime_version"])
    summary.add_row("Status", _status_text(result["status"]))
    summary.add_row("Transport", result["transport"])
    summary.add_row("Protocol", result["protocol_version"])
    summary.add_row("Identity", result["identity"]["path"])
    summary.add_row("Identity Hash", result["identity"]["sha256"][:12])
    if correlation_id:
        summary.add_row("Correlation", correlation_id)
    return Panel.fit(summary, title="Runtime Health", border_style="green")


def render_task_created(result: dict[str, Any], correlation_id: str | None) -> RenderableType:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Task ID", result["task_id"])
    summary.add_row("Run ID", result["run_id"])
    summary.add_row("Status", _status_text(result["status"]))
    summary.add_row("Accepted", result["accepted_at"])
    if correlation_id:
        summary.add_row("Correlation", correlation_id)
    hint = Text.assemble(
        ("Next: ", "bold"),
        (f"agent logs {result['task_id']}", "cyan"),
    )
    return Group(
        Panel.fit(summary, title="Task Accepted", border_style="green"),
        Panel.fit(hint, border_style="blue"),
    )


def render_task_snapshot(task: dict[str, Any], *, title: str = "Task Status") -> RenderableType:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Task ID", task["task_id"])
    summary.add_row("Run ID", task["run_id"])
    summary.add_row("Status", _status_text(task["status"]))
    summary.add_row("Objective", task["objective"])

    details = Table(box=None, expand=False, padding=(0, 2))
    details.add_column("Field", style="bold")
    details.add_column("Value")
    optional_fields = (
        ("Phase", "current_phase"),
        ("Summary", "latest_summary"),
        ("Active Subagent", "active_subagent"),
        ("Artifacts", "artifact_count"),
        ("Last Event", "last_event_at"),
        ("Pause Reason", "pause_reason"),
        ("Checkpoint Thread", "checkpoint_thread_id"),
        ("Checkpoint", "latest_checkpoint_id"),
    )
    has_details = False
    for label, key in optional_fields:
        value = task.get(key)
        if value is not None:
            details.add_row(label, str(value))
            has_details = True

    failure = task.get("failure")
    failure_panel: RenderableType | None = None
    if isinstance(failure, dict) and failure.get("message"):
        failure_panel = Panel(
            str(failure["message"]),
            title="Failure",
            border_style="red",
        )

    items: list[RenderableType] = [summary]
    if has_details:
        items.append(details)
    if failure_panel is not None:
        items.append(failure_panel)
    return Panel(Group(*items), title=title, border_style=_border_for_status(task["status"]))


def render_logs_stream_open(task_id: str, run_id: str, stream_open: bool) -> RenderableType:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Task ID", task_id)
    summary.add_row("Run ID", run_id)
    summary.add_row("Stream", "open" if stream_open else "closed")
    return Panel.fit(summary, title="Event Stream", border_style="blue")


def render_event_timeline(event_payloads: list[dict[str, Any]]) -> list[RenderableType]:
    return [format_event(event_payload["event"]) for event_payload in event_payloads]


def format_event(event: dict[str, Any]) -> RenderableType:
    event_type = str(event["event_type"])
    payload = event.get("payload", {})
    timestamp = payload.get("timestamp")
    prefix = Text()
    if timestamp:
        prefix.append(f"{timestamp} ", style="dim")
    prefix.append(f"{event_type:<24}", style="bold cyan")
    prefix.append(_format_event_message(event_type, payload))
    return prefix


def _format_event_message(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "task.created":
        return f" objective={payload.get('objective', '<unknown>')}"
    if event_type == "task.started":
        return " execution started"
    if event_type == "checkpoint.saved":
        return f" {payload.get('checkpoint_id') or 'checkpoint recorded'}"
    if event_type == "task.paused":
        return f" {payload.get('reason') or payload.get('summary') or 'paused'}"
    if event_type == "task.user_input_received":
        return f" {payload.get('summary') or 'user input received'}"
    if event_type == "task.resumed":
        return f" {payload.get('summary') or 'execution resumed'}"
    if event_type == "recovery.discovered":
        return f" {payload.get('summary') or 'recovered resumable run'}"
    if event_type == "plan.updated":
        return f" {payload.get('summary') or payload.get('plan') or 'plan updated'}"
    if event_type == "subagent.started":
        subagent_id = payload.get("subagentId") or "primary"
        task_description = payload.get("taskDescription")
        if task_description:
            return f" {subagent_id} started: {task_description}"
        return f" {subagent_id}"
    if event_type == "subagent.completed":
        subagent_id = payload.get("subagentId") or "primary"
        status = payload.get("status") or "completed"
        duration = payload.get("duration")
        if duration is not None:
            return f" {subagent_id} status={status} duration={duration}"
        return f" {subagent_id} status={status}"
    if event_type == "tool.called":
        tool = payload.get("tool") or "unknown-tool"
        arguments = payload.get("arguments")
        if arguments:
            return f" {tool} {json.dumps(arguments, sort_keys=True)}"
        return f" {tool}"
    if event_type == "artifact.created":
        artifact = payload.get("artifact", {})
        return f" {artifact.get('logical_path') or '<unknown-artifact>'}"
    if event_type == "skill.install.requested":
        return f" {payload.get('source_path') or 'skill install requested'}"
    if event_type == "skill.install.validated":
        validation = payload.get("validation", {})
        return f" validation={validation.get('status', 'unknown')}"
    if event_type == "skill.install.approval_requested":
        approval = payload.get("approval", {})
        return f" approval={approval.get('approval_id') or 'requested'}"
    if event_type == "skill.install.completed":
        return f" {payload.get('target_path') or 'skill install completed'}"
    if event_type == "skill.install.failed":
        return f" {payload.get('summary') or 'skill install failed'}"
    if event_type == "task.completed":
        return f" {payload.get('summary') or 'success'}"
    if event_type == "task.failed":
        return f" {payload.get('error') or payload.get('summary') or 'failed'}"
    if payload.get("summary"):
        return f" {payload['summary']}"
    return f" {json.dumps(payload, sort_keys=True)}"


def render_artifacts(artifacts: list[dict[str, Any]]) -> RenderableType:
    if not artifacts:
        return _empty_panel("Artifacts", "No runtime artifacts were found for this task.")
    table = Table(title="Artifacts", header_style="bold magenta")
    table.add_column("Artifact ID", style="cyan", no_wrap=True)
    table.add_column("Logical Path", no_wrap=True)
    table.add_column("Type", no_wrap=True)
    table.add_column("Persistence", no_wrap=True)
    table.add_column("Display Name", no_wrap=True)
    for artifact in artifacts:
        table.add_row(
            artifact["artifact_id"],
            artifact["logical_path"],
            artifact["content_type"],
            artifact["persistence_class"],
            str(artifact.get("display_name") or "-"),
        )
    return table


def render_skill_install(result: dict[str, Any]) -> RenderableType:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Status", _status_text(result["status"]))
    summary.add_row("Target Path", result["target_path"])
    summary.add_row("Approval Required", str(result["approval_required"]))
    summary.add_row("Validation", result["validation"]["status"])
    summary.add_row("Summary", result["summary"])
    if result.get("approval_id") is not None:
        summary.add_row("Approval ID", str(result["approval_id"]))
    summary.add_row("Findings", str(len(result["validation"].get("findings", []))))
    artifacts = result.get("artifacts", [])
    if artifacts:
        artifact_table = Table(box=None, expand=False, padding=(0, 1))
        artifact_table.add_column("Artifacts", style="bold")
        for artifact in artifacts:
            artifact_table.add_row(str(artifact))
        return Panel(Group(summary, artifact_table), title="Skill Install", border_style="green")
    return Panel.fit(summary, title="Skill Install", border_style="green")


def render_approvals(approvals: list[dict[str, Any]]) -> RenderableType:
    if not approvals:
        return _empty_panel("Approvals", "No approvals are pending or recorded for this task.")
    table = Table(title="Approvals", header_style="bold magenta")
    table.add_column("Approval ID", style="cyan", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Type", no_wrap=True)
    table.add_column("Scope", no_wrap=True)
    table.add_column("Decision", no_wrap=True)
    table.add_column("Created", no_wrap=True)
    table.add_column("Description")
    for approval in approvals:
        table.add_row(
            approval["approval_id"],
            approval["status"],
            approval["type"],
            approval["scope_summary"],
            str(approval.get("decision") or "-"),
            approval["created_at"],
            str(approval.get("description") or "-"),
        )
    return table


def render_approval_result(result: dict[str, Any]) -> RenderableType:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Approval ID", result["approval_id"])
    summary.add_row("Accepted", str(result["accepted"]))
    summary.add_row("Status", result["status"])
    return Panel.fit(summary, title="Approval Submitted", border_style="green")


def render_diagnostics(diagnostics: list[dict[str, Any]]) -> RenderableType:
    if not diagnostics:
        return _empty_panel("Diagnostics", "No diagnostics were persisted for this task.")
    table = Table(title="Diagnostics", header_style="bold magenta")
    table.add_column("Diagnostic ID", style="cyan", no_wrap=True)
    table.add_column("Kind", no_wrap=True)
    table.add_column("Created", no_wrap=True)
    table.add_column("Message")
    table.add_column("Details")
    for diagnostic in diagnostics:
        details = diagnostic.get("details")
        table.add_row(
            diagnostic["diagnostic_id"],
            diagnostic["kind"],
            diagnostic["created_at"],
            diagnostic["message"],
            json.dumps(details, sort_keys=True) if details else "-",
        )
    return table


def render_memory(entries: list[dict[str, Any]], *, scope: str, count: int) -> RenderableType:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Scope", scope)
    summary.add_row("Count", str(count))
    if not entries:
        return Panel.fit(summary, title="Memory", border_style="blue")

    table = Table(title="Memory Entries", header_style="bold magenta")
    table.add_column("Memory ID", style="cyan", no_wrap=True)
    table.add_column("Namespace", no_wrap=True)
    table.add_column("Summary")
    table.add_column("Source Run", no_wrap=True)
    table.add_column("Updated", no_wrap=True)
    table.add_column("Provenance", no_wrap=True)
    for entry in entries:
        provenance = entry.get("provenance")
        table.add_row(
            entry["memory_id"],
            entry["namespace"],
            entry["summary"],
            str(entry.get("source_run") or "-"),
            entry["updated_at"],
            json.dumps(provenance, sort_keys=True) if provenance else "-",
        )
    return Group(Panel.fit(summary, title="Memory", border_style="blue"), table)


def render_config(result: dict[str, Any]) -> RenderableType:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Loaded Profiles", ", ".join(result.get("loaded_profiles", [])) or "<none>")
    summary.add_row("Config Sources", ", ".join(result.get("config_sources", [])) or "<none>")
    summary.add_row("Redactions", str(len(result.get("redactions", []))))
    return Group(
        Panel.fit(summary, title="Runtime Config", border_style="blue"),
        Panel(JSON.from_data(result["effective_config"]), title="Effective Config"),
    )


def _status_text(status: str) -> Text:
    styles = {
        "accepted": "bold green",
        "completed": "bold green",
        "healthy": "bold green",
        "pending": "bold yellow",
        "paused": "bold yellow",
        "running": "bold blue",
        "failed": "bold red",
        "rejected": "bold red",
    }
    return Text(str(status), style=styles.get(status, "bold"))


def _border_for_status(status: str) -> str:
    if status in {"completed", "accepted"}:
        return "green"
    if status in {"paused", "pending"}:
        return "yellow"
    if status in {"failed", "rejected"}:
        return "red"
    return "blue"


def _empty_panel(title: str, message: str) -> RenderableType:
    return Panel.fit(message, title=title, border_style="blue")
