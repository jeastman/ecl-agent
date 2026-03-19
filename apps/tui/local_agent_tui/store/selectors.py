from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, cast

from rich.text import Text as _RichText

from .app_state import AppState, TaskEventRecord
from ..theme.colors import (
    TEXT_PRIMARY as _TEXT_PRIMARY,
    TEXT_SECONDARY as _TEXT_SECONDARY,
    TEXT_MUTED_DEEP as _TEXT_MUTED_DEEP,
)
from ..utils.time_format import relative_time as _relative_time
from ..utils.text import truncate_id as _truncate_id


@dataclass(frozen=True, slots=True)
class TaskListItemViewModel:
    task_id: str
    run_id: str
    status: str
    objective: str
    updated_at: str
    awaiting_approval: bool
    artifact_count: int
    is_selected: bool
    is_highlighted: bool


@dataclass(frozen=True, slots=True)
class TaskSummaryViewModel:
    task_id: str
    run_id: str
    status: str
    objective: str
    latest_summary: str
    created_at: str
    updated_at: str
    awaiting_approval: bool
    artifact_count: int
    actionable_label: str
    actionable_hint: str


@dataclass(frozen=True, slots=True)
class ApprovalQueueItemViewModel:
    approval_id: str
    task_id: str
    run_id: str
    status: str
    request_type: str
    policy_context: str
    requested_action: str
    description: str
    scope_summary: str
    created_at: str
    created_at_relative: str
    is_selected: bool
    is_highlighted: bool


@dataclass(frozen=True, slots=True)
class ApprovalDetailViewModel:
    approval_id: str
    task_id: str
    run_id: str
    request_type: str
    policy_context: str
    requested_action: str
    description: str
    scope_summary: str
    status: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ArtifactItemViewModel:
    artifact_id: str
    task_id: str
    run_id: str
    logical_path: str
    display_name: str
    content_type: str
    created_at: str
    created_at_relative: str


@dataclass(frozen=True, slots=True)
class TaskDetailHeaderViewModel:
    task_id: str
    run_id: str
    status: str
    created_at: str
    updated_at: str
    objective: str
    current_phase: str
    active_subagent: str | None
    actionable_label: str
    actionable_hint: str


@dataclass(frozen=True, slots=True)
class TimelineEventViewModel:
    timestamp: str
    event_type: str
    summary: str
    severity: str
    repeat_count: int
    source_name: str | None
    highlight: bool
    highlight_label: str | None


@dataclass(frozen=True, slots=True)
class TimelineGroupViewModel:
    events: list[TimelineEventViewModel]
    filter_label: str
    search_query: str


@dataclass(frozen=True, slots=True)
class PlanHistoryItemViewModel:
    timestamp: str
    summary: str
    phase: str


@dataclass(frozen=True, slots=True)
class PlanViewModel:
    current_phase: str
    current_step: str
    recent_updates: list[PlanHistoryItemViewModel]


@dataclass(frozen=True, slots=True)
class SubagentActivityItemViewModel:
    subagent_id: str
    status: str
    started_at: str | None
    completed_at: str | None
    latest_summary: str


@dataclass(frozen=True, slots=True)
class ArtifactPanelItemViewModel:
    artifact_id: str
    display_name: str
    logical_path: str
    content_type: str
    created_at: str
    is_selected: bool


@dataclass(frozen=True, slots=True)
class TaskActionBarViewModel:
    resume_enabled: bool
    approvals_enabled: bool
    artifact_open_enabled: bool
    artifact_external_open_enabled: bool
    diagnostics_enabled: bool
    logs_toggle_enabled: bool
    logs_visible: bool
    back_enabled: bool
    input_placeholder: str
    status_message: str


@dataclass(frozen=True, slots=True)
class NotificationStripItemViewModel:
    timestamp: str
    summary: str
    severity: str


@dataclass(frozen=True, slots=True)
class NotificationStripViewModel:
    items: list[NotificationStripItemViewModel]


@dataclass(frozen=True, slots=True)
class ArtifactBrowserToolbarViewModel:
    group_by: str
    total_count: int


@dataclass(frozen=True, slots=True)
class ArtifactBrowserRowViewModel:
    artifact_id: str
    task_id: str
    run_id: str
    group_label: str
    display_name: str
    content_type: str
    created_at: str
    logical_path: str
    is_selected: bool
    is_highlighted: bool


@dataclass(frozen=True, slots=True)
class ArtifactPreviewViewModel:
    artifact_id: str | None
    title: str
    status: str
    body: str
    content_type: str | None
    open_label: str
    external_open_supported: bool
    render_as_markdown: bool


@dataclass(frozen=True, slots=True)
class MarkdownArtifactViewModel:
    artifact_id: str
    display_name: str
    body: str
    status: str
    error: str | None


@dataclass(frozen=True, slots=True)
class MemoryGroupItemViewModel:
    group_id: str
    title: str
    description: str
    count: int
    is_selected: bool


@dataclass(frozen=True, slots=True)
class MemoryEntryItemViewModel:
    memory_id: str
    title: str
    subtitle: str
    is_selected: bool


@dataclass(frozen=True, slots=True)
class MemoryDetailViewModel:
    title: str
    status: str
    summary: str
    content: str
    raw_scope: str
    namespace: str
    provenance: str
    source_run: str
    confidence: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ConfigSectionItemViewModel:
    section_id: str
    title: str
    description: str
    is_selected: bool


@dataclass(frozen=True, slots=True)
class ConfigDetailViewModel:
    title: str
    status: str
    summary: str
    body: str


@dataclass(frozen=True, slots=True)
class CommandPaletteItemViewModel:
    command_id: str
    label: str
    hint: str
    is_selected: bool
    match_spans: list[tuple[int, int]]


@dataclass(frozen=True, slots=True)
class CommandPaletteViewModel:
    query: str
    items: list[CommandPaletteItemViewModel]


@dataclass(frozen=True, slots=True)
class TimelineFilterOptionViewModel:
    filter_id: str
    label: str


@dataclass(frozen=True, slots=True)
class TimelineStateSummaryViewModel:
    filter_label: str
    search_query: str


@dataclass(frozen=True, slots=True)
class LogEntryViewModel:
    timestamp: str
    level: str
    source_name: str | None
    message: str
    is_highlighted: bool


@dataclass(frozen=True, slots=True)
class LogViewModel:
    lines: list[LogEntryViewModel]


@dataclass(frozen=True, slots=True)
class DiagnosticsItemViewModel:
    diagnostic_id: str
    kind: str
    created_at: str
    message: str
    is_selected: bool


@dataclass(frozen=True, slots=True)
class DiagnosticsDetailViewModel:
    title: str
    status: str
    summary: str
    body: str


_SCREEN_DISPLAY_NAMES: dict[str, str] = {
    "dashboard": "Dashboard",
    "task_detail": "Task",
    "approvals": "Approvals",
    "artifacts": "Artifacts",
    "memory": "Memory",
    "config": "Config",
    "diagnostics": "Diagnostics",
    "markdown_viewer": "Viewer",
}


def screen_breadcrumb(state: AppState) -> _RichText:
    """Return a Rich Text breadcrumb from the navigation stack.

    Screen names use TEXT_SECONDARY; the current (last) screen uses TEXT_PRIMARY.
    Separators use TEXT_MUTED_DEEP. task_detail nodes show the truncated task ID.
    Colors imported from theme.colors — not theme.typography.
    """
    result = _RichText()
    stack = state.navigation_stack or ["dashboard"]
    for index, screen in enumerate(stack):
        is_last = index == len(stack) - 1
        color = _TEXT_PRIMARY if is_last else _TEXT_SECONDARY

        if screen == "task_detail":
            task_id = state.selected_task_id or ""
            short_id = _truncate_id(task_id, width=16) if task_id else ""
            label = f"Task {short_id}".strip()
        else:
            label = _SCREEN_DISPLAY_NAMES.get(screen, screen)

        if index > 0:
            result.append(" › ", style=_TEXT_MUTED_DEEP)
        result.append(label, style=color)
    return result


def connection_label(state: AppState) -> str:
    if state.connection_status == "error" and state.last_error:
        return f"{state.connection_status} ({state.last_error})"
    return state.connection_status


def runtime_health_label(state: AppState) -> str:
    if not state.runtime_health:
        return "unknown"
    return str(state.runtime_health.get("status", "unknown"))


def task_count(state: AppState) -> int:
    return len(_sorted_task_snapshots(state))


def approval_count(state: AppState) -> int:
    return len(pending_approvals(state))


def artifact_count(state: AppState) -> int:
    return sum(len(artifacts) for artifacts in state.artifacts_by_task.values())


def diagnostics_count(state: AppState) -> int:
    return sum(len(diagnostics) for diagnostics in state.diagnostics_by_task.values())


def recent_task_ids(state: AppState) -> list[str]:
    return [str(task["task_id"]) for task in _sorted_task_snapshots(state)]


def recent_tasks(state: AppState, *, limit: int = 10) -> list[TaskListItemViewModel]:
    items: list[TaskListItemViewModel] = []
    highlighted_task_ids = _highlighted_task_ids(state)
    for task in _sorted_task_snapshots(state)[:limit]:
        items.append(
            TaskListItemViewModel(
                task_id=str(task["task_id"]),
                run_id=str(task.get("run_id", "")),
                status=str(task.get("status", "unknown")),
                objective=str(task.get("objective", "")),
                updated_at=str(task.get("last_event_at") or task.get("updated_at") or ""),
                awaiting_approval=bool(task.get("awaiting_approval", False)),
                artifact_count=_int_value(task.get("artifact_count", 0)),
                is_selected=state.selected_task_id == task["task_id"],
                is_highlighted=str(task["task_id"]) in highlighted_task_ids,
            )
        )
    return items


def running_tasks(state: AppState) -> list[TaskListItemViewModel]:
    return [item for item in recent_tasks(state) if item.status in {"executing", "planning"}]


def selected_task_summary(state: AppState) -> TaskSummaryViewModel | None:
    if state.selected_task_id is None:
        return None
    task = state.task_snapshots.get(state.selected_task_id)
    if task is None:
        return None
    return TaskSummaryViewModel(
        task_id=str(task["task_id"]),
        run_id=str(task.get("run_id", "")),
        status=str(task.get("status", "unknown")),
        objective=str(task.get("objective", "")),
        latest_summary=str(task.get("latest_summary") or "Waiting for runtime updates."),
        created_at=str(task.get("created_at", "")),
        updated_at=str(task.get("last_event_at") or task.get("updated_at") or ""),
        awaiting_approval=bool(task.get("awaiting_approval", False)),
        artifact_count=_int_value(task.get("artifact_count", 0)),
        actionable_label=_actionable_status_label(task),
        actionable_hint=_actionable_status_hint(task),
    )


def selected_task_header(state: AppState) -> TaskDetailHeaderViewModel | None:
    task = _selected_task(state)
    if task is None:
        return None
    return TaskDetailHeaderViewModel(
        task_id=str(task["task_id"]),
        run_id=str(task.get("run_id", "")),
        status=str(task.get("status", "unknown")),
        created_at=str(task.get("created_at", "")),
        updated_at=str(task.get("last_event_at") or task.get("updated_at") or ""),
        objective=str(task.get("objective", "")),
        current_phase=str(task.get("current_phase") or "unknown"),
        active_subagent=_str_or_none(task.get("active_subagent")),
        actionable_label=_actionable_status_label(task),
        actionable_hint=_actionable_status_hint(task),
    )


def pending_approvals(
    state: AppState,
    *,
    limit: int | None = None,
) -> list[ApprovalQueueItemViewModel]:
    approvals: list[ApprovalQueueItemViewModel] = []
    highlighted_approval_ids = _highlighted_approval_ids(state)
    for entries in state.approvals_by_task.values():
        for approval in entries:
            status = str(approval.get("status", "pending"))
            if status not in {"pending", "waiting"}:
                continue
            approval_id = str(approval.get("approval_id", ""))
            approvals.append(
                ApprovalQueueItemViewModel(
                    approval_id=approval_id,
                    task_id=str(approval.get("task_id", "")),
                    run_id=str(approval.get("run_id", "")),
                    status=status,
                    request_type=_approval_request_type(approval),
                    policy_context=_approval_policy_context(approval),
                    requested_action=_approval_requested_action(approval),
                description=str(
                        approval.get("description") or approval.get("type") or "Approval"
                    ),
                    scope_summary=str(approval.get("scope_summary") or "Pending review"),
                    created_at=str(approval.get("created_at", "")),
                    created_at_relative=_relative_time(str(approval.get("created_at", ""))),
                    is_selected=state.selected_approval_id == approval_id,
                    is_highlighted=approval_id in highlighted_approval_ids,
                )
            )
    approvals.sort(key=lambda item: item.created_at, reverse=True)
    if limit is not None:
        approvals = approvals[:limit]
    return approvals


def pending_approvals_for_selected_task(
    state: AppState,
    *,
    limit: int | None = None,
) -> list[ApprovalQueueItemViewModel]:
    approvals = selected_task_pending_approvals(state)
    if limit is not None:
        approvals = approvals[:limit]
    return approvals


def selected_approval_detail(state: AppState) -> ApprovalDetailViewModel | None:
    approval = _selected_approval(state)
    if approval is None:
        return None
    return ApprovalDetailViewModel(
        approval_id=str(approval.get("approval_id", "")),
        task_id=str(approval.get("task_id", "")),
        run_id=str(approval.get("run_id", "")),
        request_type=_approval_request_type(approval),
        policy_context=_approval_policy_context(approval),
        requested_action=_approval_requested_action(approval),
        description=str(approval.get("description") or approval.get("type") or "Approval"),
        scope_summary=str(approval.get("scope_summary") or "Pending review"),
        status=str(approval.get("status", "pending")),
        created_at=str(approval.get("created_at", "")),
    )


def recent_artifacts(state: AppState, *, limit: int = 5) -> list[ArtifactItemViewModel]:
    artifacts: list[ArtifactItemViewModel] = []
    for entries in state.artifacts_by_task.values():
        for artifact in entries:
            artifacts.append(_artifact_item_view_model(artifact))
    artifacts.sort(key=lambda item: item.created_at, reverse=True)
    return artifacts[:limit]


def task_timeline(state: AppState) -> TimelineGroupViewModel:
    events = _filtered_task_events(state)
    collapsed: list[TimelineEventViewModel] = []
    for event in events:
        current = _timeline_event(event)
        previous = collapsed[-1] if collapsed else None
        if (
            previous is not None
            and previous.event_type == current.event_type
            and previous.summary == current.summary
            and previous.source_name == current.source_name
            and _should_collapse_timeline_event(current.event_type)
        ):
            collapsed[-1] = TimelineEventViewModel(
                timestamp=current.timestamp,
                event_type=previous.event_type,
                summary=previous.summary,
                severity=previous.severity,
                repeat_count=previous.repeat_count + 1,
                source_name=previous.source_name,
                highlight=previous.highlight or current.highlight,
                highlight_label=previous.highlight_label or current.highlight_label,
            )
            continue
        collapsed.append(current)
    summary = timeline_state_summary(state)
    return TimelineGroupViewModel(
        events=collapsed,
        filter_label=summary.filter_label,
        search_query=summary.search_query,
    )


def task_plan_view(state: AppState) -> PlanViewModel:
    task = _selected_task(state)
    if task is None:
        return PlanViewModel(
            current_phase="unknown",
            current_step="No task selected.",
            recent_updates=[],
        )
    plan_events = [
        event for event in _selected_task_events(state) if event.event_type == "plan.updated"
    ]
    recent_updates = [
        PlanHistoryItemViewModel(
            timestamp=event.timestamp,
            summary=event.summary,
            phase=str(event.payload.get("phase") or task.get("current_phase") or "unknown"),
        )
        for event in plan_events[-5:]
    ]
    current_step = str(
        task.get("latest_summary")
        or (recent_updates[-1].summary if recent_updates else "")
        or "Waiting for plan updates."
    )
    return PlanViewModel(
        current_phase=str(task.get("current_phase") or "unknown"),
        current_step=current_step,
        recent_updates=recent_updates,
    )


def task_subagent_activity(state: AppState) -> list[SubagentActivityItemViewModel]:
    task = _selected_task(state)
    items: dict[str, SubagentActivityItemViewModel] = {}
    for event in _selected_task_events(state):
        subagent_id = _subagent_id(event)
        if subagent_id is None:
            continue
        current = items.get(
            subagent_id,
            SubagentActivityItemViewModel(
                subagent_id=subagent_id,
                status="UNKNOWN",
                started_at=None,
                completed_at=None,
                latest_summary="",
            ),
        )
        if event.event_type == "subagent.started":
            items[subagent_id] = SubagentActivityItemViewModel(
                subagent_id=subagent_id,
                status="RUNNING",
                started_at=event.timestamp,
                completed_at=current.completed_at,
                latest_summary=str(event.payload.get("taskDescription") or event.summary),
            )
        elif event.event_type == "subagent.completed":
            items[subagent_id] = SubagentActivityItemViewModel(
                subagent_id=subagent_id,
                status=str(event.payload.get("status", "completed")).upper(),
                started_at=current.started_at,
                completed_at=event.timestamp,
                latest_summary=str(event.payload.get("summary") or event.summary),
            )
    active_subagent = _str_or_none(task.get("active_subagent")) if task is not None else None
    if active_subagent and active_subagent not in items:
        items[active_subagent] = SubagentActivityItemViewModel(
            subagent_id=active_subagent,
            status="RUNNING",
            started_at=None,
            completed_at=None,
            latest_summary=str(task.get("latest_summary") or "Subagent is running."),
        )
    return list(items.values())


def task_artifact_panel(state: AppState) -> list[ArtifactPanelItemViewModel]:
    task_key = _selected_task_key(state)
    if task_key is None:
        return []
    selected_artifact_id = state.selected_artifact_id_by_task.get(task_key)
    artifacts = list(state.artifacts_by_task.get(task_key, []))
    artifacts.sort(key=lambda artifact: str(artifact.get("created_at", "")), reverse=True)
    return [
        ArtifactPanelItemViewModel(
            artifact_id=str(artifact.get("artifact_id", "")),
            display_name=str(
                artifact.get("display_name")
                or artifact.get("logical_path")
                or artifact.get("artifact_id")
                or "artifact"
            ),
            logical_path=str(artifact.get("logical_path", "")),
            content_type=str(artifact.get("content_type", "unknown")),
            created_at=str(artifact.get("created_at", "")),
            is_selected=str(artifact.get("artifact_id", "")) == selected_artifact_id,
        )
        for artifact in artifacts
    ]


def task_notifications(state: AppState) -> NotificationStripViewModel:
    priority_events = [
        event
        for event in _selected_task_events(state)
        if event.event_type
        in {
            "approval.requested",
            "task.failed",
            "artifact.created",
            "task.completed",
            "task.resumed",
            "task.user_input_received",
        }
    ]
    priority_events = priority_events[-3:]
    return NotificationStripViewModel(
        items=[
            NotificationStripItemViewModel(
                timestamp=event.timestamp,
                summary=event.summary,
                severity=event.severity,
            )
            for event in priority_events
        ]
    )


def task_action_bar(state: AppState) -> TaskActionBarViewModel:
    task = _selected_task(state)
    artifacts = task_artifact_panel(state)
    approvals_enabled = bool(selected_task_pending_approvals(state))
    resume_enabled = False
    diagnostics_enabled = _selected_task_key(state) is not None
    artifact_external_open_enabled = selected_artifact_preview(state).external_open_supported
    status_message = state.task_input_feedback or _actionable_status_hint(task)
    input_placeholder = "Enter a task command and press Enter"
    if task is not None:
        links = task.get("links", {})
        resume_enabled = bool(task.get("is_resumable")) or (
            isinstance(links, dict) and links.get("resume") == "task.resume"
        )
        if str(task.get("pause_reason", "")).lower() == "awaiting_user_input":
            input_placeholder = "Type: reply <message>"
    return TaskActionBarViewModel(
        resume_enabled=resume_enabled,
        approvals_enabled=approvals_enabled,
        artifact_open_enabled=bool(artifacts),
        artifact_external_open_enabled=artifact_external_open_enabled,
        diagnostics_enabled=diagnostics_enabled,
        logs_toggle_enabled=_selected_task_key(state) is not None,
        logs_visible=state.task_detail_show_logs,
        back_enabled=True,
        input_placeholder=input_placeholder,
        status_message=status_message,
    )


def artifact_browser_toolbar(state: AppState) -> ArtifactBrowserToolbarViewModel:
    return ArtifactBrowserToolbarViewModel(
        group_by=state.artifact_group_by,
        total_count=len(_all_artifacts(state)),
    )


def artifact_browser_rows(state: AppState) -> list[ArtifactBrowserRowViewModel]:
    rows: list[ArtifactBrowserRowViewModel] = []
    selected_id = _selected_artifact_browser_id(state)
    highlighted_artifact_ids = _highlighted_artifact_ids(state)
    for artifact in _all_artifacts(state):
        rows.append(
            ArtifactBrowserRowViewModel(
                artifact_id=str(artifact.get("artifact_id", "")),
                task_id=str(artifact.get("task_id", "")),
                run_id=str(artifact.get("run_id", "")),
                group_label=_artifact_group_label(artifact, state.artifact_group_by),
                display_name=_artifact_display_name(artifact),
                content_type=str(artifact.get("content_type", "unknown")),
                created_at=str(artifact.get("created_at", "")),
                logical_path=str(artifact.get("logical_path", "")),
                is_selected=str(artifact.get("artifact_id", "")) == selected_id,
                is_highlighted=str(artifact.get("artifact_id", "")) in highlighted_artifact_ids,
            )
        )
    return rows


def selected_artifact_preview(state: AppState) -> ArtifactPreviewViewModel:
    artifact = selected_artifact_browser_item(state)
    if artifact is None:
        return ArtifactPreviewViewModel(
            artifact_id=None,
            title="Artifact Preview",
            status="empty",
            body="Select an artifact to inspect its preview.",
            content_type=None,
            open_label="Unavailable",
            external_open_supported=False,
            render_as_markdown=False,
        )
    artifact_id = str(artifact.get("artifact_id", ""))
    preview_payload = state.artifact_preview_cache.get(artifact_id)
    preview_status = state.artifact_preview_status_by_artifact.get(artifact_id, "idle")
    preview_error = state.artifact_preview_error_by_artifact.get(artifact_id)
    if preview_status == "loading":
        return ArtifactPreviewViewModel(
            artifact_id=artifact_id,
            title=_artifact_display_name(artifact),
            status="loading",
            body="Loading preview...",
            content_type=str(artifact.get("content_type", "unknown")),
            open_label=_artifact_open_label(artifact),
            external_open_supported=False,
            render_as_markdown=False,
        )
    if preview_error:
        return ArtifactPreviewViewModel(
            artifact_id=artifact_id,
            title=_artifact_display_name(artifact),
            status="error",
            body=preview_error,
            content_type=str(artifact.get("content_type", "unknown")),
            open_label=_artifact_open_label(artifact),
            external_open_supported=False,
            render_as_markdown=False,
        )
    if not isinstance(preview_payload, dict):
        return ArtifactPreviewViewModel(
            artifact_id=artifact_id,
            title=_artifact_display_name(artifact),
            status="idle",
            body="Preview not loaded yet.",
            content_type=str(artifact.get("content_type", "unknown")),
            open_label=_artifact_open_label(artifact),
            external_open_supported=False,
            render_as_markdown=False,
        )
    preview = dict(preview_payload.get("preview", {}))
    body = str(preview.get("text") or preview.get("message") or "Preview unavailable.")
    if preview.get("truncated"):
        body = f"{body}\n\n[truncated]"
    return ArtifactPreviewViewModel(
        artifact_id=artifact_id,
        title=_artifact_display_name(artifact),
        status="loaded",
        body=body,
        content_type=str(artifact.get("content_type", "unknown")),
        open_label=_artifact_open_label(
            artifact,
            external_open_supported=bool(preview_payload.get("external_open_supported", False)),
        ),
        external_open_supported=bool(preview_payload.get("external_open_supported", False)),
        render_as_markdown=str(artifact.get("content_type", "unknown")) == "text/markdown",
    )


def selected_markdown_artifact(state: AppState) -> MarkdownArtifactViewModel | None:
    artifact_id = state.markdown_viewer_artifact_id
    if artifact_id is None:
        return None
    artifact = _artifact_by_id(state, artifact_id)
    display_name = _artifact_display_name(artifact) if artifact is not None else artifact_id
    preview_payload = state.artifact_preview_cache.get(artifact_id)
    preview_status = state.artifact_preview_status_by_artifact.get(artifact_id, "idle")
    preview_error = state.artifact_preview_error_by_artifact.get(artifact_id)
    if artifact is None:
        return MarkdownArtifactViewModel(
            artifact_id=artifact_id,
            display_name=display_name,
            body="Markdown artifact unavailable.",
            status="empty",
            error=None,
        )
    if preview_status == "failed":
        return MarkdownArtifactViewModel(
            artifact_id=artifact_id,
            display_name=display_name,
            body=preview_error or "Markdown preview unavailable.",
            status="failed",
            error=preview_error,
        )
    if preview_payload is None:
        return MarkdownArtifactViewModel(
            artifact_id=artifact_id,
            display_name=display_name,
            body="Loading markdown artifact...",
            status="loading",
            error=None,
        )
    preview = dict(preview_payload.get("preview", {}))
    body = str(preview.get("text") or "")
    if preview.get("truncated"):
        body = f"{body}\n\n[truncated]".strip()
    if not body:
        body = "Markdown artifact is empty."
    return MarkdownArtifactViewModel(
        artifact_id=artifact_id,
        display_name=display_name,
        body=body,
        status="loaded",
        error=None,
    )


def selected_artifact_browser_item(state: AppState) -> dict[str, Any] | None:
    artifact_id = _selected_artifact_browser_id(state)
    if artifact_id is None:
        return None
    return _artifact_by_id(state, artifact_id)


def selected_task_pending_approvals(state: AppState) -> list[ApprovalQueueItemViewModel]:
    if state.selected_task_id is None:
        return []
    return [
        approval
        for approval in pending_approvals(state)
        if approval.task_id == state.selected_task_id
    ]


def command_palette(state: AppState) -> CommandPaletteViewModel:
    commands = [
        ("create_task", "Create task", "New task from workspace", True),
        (
            "resume_task",
            "Resume task",
            "Continue paused selected task",
            task_action_bar(state).resume_enabled,
        ),
        (
            "approve_request",
            "Approve request",
            "Jump directly into the pending approval workflow",
            bool(pending_approvals(state)),
        ),
        ("open_artifacts", "Inspect artifacts", "Browse runtime artifacts", True),
        ("open_memory", "Inspect memory", "Open memory inspector", True),
        ("open_config", "View runtime config", "Inspect effective runtime config", True),
        (
            "open_diagnostics",
            "View diagnostics",
            "Inspect persisted task diagnostics",
            _selected_task_key(state) is not None,
        ),
        (
            "reconnect_runtime",
            "Reconnect runtime",
            "Reconnect and recover the current TUI context",
            True,
        ),
    ]
    raw_query = state.command_palette_query.strip()
    query = raw_query.lower()
    items: list[CommandPaletteItemViewModel] = []
    if query.startswith("/"):
        task_id = raw_query[1:]
        for task in _sorted_task_snapshots(state):
            candidate_task_id = str(task.get("task_id", ""))
            if candidate_task_id.lower() == task_id.lower():
                items.append(
                    CommandPaletteItemViewModel(
                        command_id=f"open_task::{candidate_task_id}",
                        label=f"Open {candidate_task_id}",
                        hint="Jump directly to task detail",
                        is_selected=True,
                        match_spans=[(5, 5 + len(candidate_task_id))],
                    )
                )
                return CommandPaletteViewModel(query=state.command_palette_query, items=items)
    for command_id, label, hint, available in commands:
        if not available:
            continue
        haystack = f"{label} {hint} {command_id.replace('_', ' ')}".lower()
        match_spans = _command_match_spans(query, label) if query else []
        if query and not (_matches_command_query(query, haystack) or match_spans):
            continue
        items.append(
            CommandPaletteItemViewModel(
                command_id=command_id,
                label=label,
                hint=hint,
                is_selected=state.command_palette_selected_id == command_id,
                match_spans=match_spans,
            )
        )
    if items and not any(item.is_selected for item in items):
        first = items[0]
        items[0] = CommandPaletteItemViewModel(
            command_id=first.command_id,
            label=first.label,
            hint=first.hint,
            is_selected=True,
            match_spans=first.match_spans,
        )
    return CommandPaletteViewModel(query=state.command_palette_query, items=items)


def timeline_filter_options() -> list[TimelineFilterOptionViewModel]:
    return [
        TimelineFilterOptionViewModel("all", "all"),
        TimelineFilterOptionViewModel("important", "important"),
        TimelineFilterOptionViewModel("tools", "tools"),
        TimelineFilterOptionViewModel("plans", "plans"),
        TimelineFilterOptionViewModel("approvals", "approvals"),
        TimelineFilterOptionViewModel("artifacts", "artifacts"),
        TimelineFilterOptionViewModel("subagents", "subagents"),
        TimelineFilterOptionViewModel("errors", "errors"),
    ]


def timeline_state_summary(state: AppState) -> TimelineStateSummaryViewModel:
    return TimelineStateSummaryViewModel(
        filter_label=_timeline_filter_label(state.task_timeline_filter),
        search_query=state.task_timeline_search_query.strip(),
    )


def task_logs(state: AppState) -> LogViewModel:
    lines: list[LogEntryViewModel] = []
    for event in _selected_task_events(state):
        if event.event_type.startswith("task.") or event.event_type.startswith("tool."):
            lines.append(
                LogEntryViewModel(
                    timestamp=event.timestamp,
                    level=event.severity.upper(),
                    source_name=event.source_name,
                    message=event.summary,
                    is_highlighted=_is_priority_event(event.event_type),
                )
            )
    return LogViewModel(lines=lines)


def status_bar_model_name(state: AppState) -> str | None:
    models = state.config_snapshot.get("models")
    if not isinstance(models, dict):
        return None
    primary = models.get("primary")
    if isinstance(primary, dict):
        model_name = primary.get("model")
        if isinstance(model_name, str) and model_name.strip():
            return model_name
    default = models.get("default")
    if isinstance(default, dict):
        model_name = default.get("model")
        if isinstance(model_name, str) and model_name.strip():
            return model_name
    return None


def status_bar_sandbox_mode(state: AppState) -> str | None:
    policy = state.config_snapshot.get("policy")
    if not isinstance(policy, dict):
        return None
    sandbox_mode = policy.get("sandbox_mode")
    if isinstance(sandbox_mode, str) and sandbox_mode.strip():
        return sandbox_mode
    return None


def status_bar_memory_status(state: AppState) -> str:
    if state.memory_request_status == "error":
        return "ERROR"
    if state.memory_request_status == "loading":
        return "SYNC"
    if any(state.memory_entries_by_context.values()):
        return "OK"
    return "IDLE"


def diagnostics_items(state: AppState) -> list[DiagnosticsItemViewModel]:
    task_key = _selected_task_key(state)
    if task_key is None:
        return []
    items: list[DiagnosticsItemViewModel] = []
    for diagnostic in state.diagnostics_by_task.get(task_key, []):
        diagnostic_id = str(diagnostic.get("diagnostic_id", ""))
        items.append(
            DiagnosticsItemViewModel(
                diagnostic_id=diagnostic_id,
                kind=str(diagnostic.get("kind", "diagnostic")),
                created_at=str(diagnostic.get("created_at", "")),
                message=str(diagnostic.get("message", "")),
                is_selected=state.selected_diagnostic_id == diagnostic_id,
            )
        )
    items.sort(key=lambda item: item.created_at, reverse=True)
    if items and not any(item.is_selected for item in items):
        first = items[0]
        items[0] = DiagnosticsItemViewModel(
            diagnostic_id=first.diagnostic_id,
            kind=first.kind,
            created_at=first.created_at,
            message=first.message,
            is_selected=True,
        )
    return items


def selected_diagnostics_detail(state: AppState) -> DiagnosticsDetailViewModel:
    if _selected_task_key(state) is None:
        return DiagnosticsDetailViewModel(
            title="Diagnostics",
            status="empty",
            summary="No task selected.",
            body="Select a task to inspect persisted diagnostics.",
        )
    if state.diagnostics_request_status == "loading":
        return DiagnosticsDetailViewModel(
            title="Diagnostics",
            status="loading",
            summary="Loading diagnostics...",
            body="Waiting for runtime diagnostics.",
        )
    if state.diagnostics_request_status == "error":
        return DiagnosticsDetailViewModel(
            title="Diagnostics",
            status="error",
            summary="Diagnostics request failed.",
            body=state.diagnostics_request_error or "Unknown diagnostics error.",
        )
    selected = _selected_diagnostic(state)
    if selected is None:
        return DiagnosticsDetailViewModel(
            title="Diagnostics",
            status="empty",
            summary="No diagnostics available.",
            body="The selected task has no persisted diagnostics.",
        )
    details = selected.get("details")
    body = (
        json.dumps(details, indent=2, sort_keys=True)
        if isinstance(details, dict)
        else "No details."
    )
    return DiagnosticsDetailViewModel(
        title=str(selected.get("kind", "diagnostic")),
        status="loaded",
        summary=str(selected.get("message", "")),
        body="\n".join(
            [
                f"Diagnostic: {selected.get('diagnostic_id', '')}",
                f"Created: {selected.get('created_at', '')}",
                "",
                body,
            ]
        ).strip(),
    )


def memory_scope_groups(state: AppState) -> list[MemoryGroupItemViewModel]:
    grouped_entries = _memory_grouped_entries(state)
    selected_group_id = _selected_memory_group_id(state, grouped_entries)
    ordered_groups = [
        ("short_term", "Short-Term Memory", "Scratch-pad state and near-term notes."),
        ("working_context", "Working Context", "Run-state context tied to active work."),
        ("episodic", "Episodic Memory", "Longer-lived project and identity memory."),
        (
            "checkpoint_metadata",
            "Checkpoint Metadata",
            "Run-linked provenance and recovery context.",
        ),
    ]
    return [
        MemoryGroupItemViewModel(
            group_id=group_id,
            title=title,
            description=description,
            count=len(grouped_entries[group_id]),
            is_selected=group_id == selected_group_id,
        )
        for group_id, title, description in ordered_groups
    ]


def memory_entry_items(state: AppState) -> list[MemoryEntryItemViewModel]:
    grouped_entries = _memory_grouped_entries(state)
    selected_group_id = _selected_memory_group_id(state, grouped_entries)
    selected_entry_id = _selected_memory_entry_id(state, selected_group_id, grouped_entries)
    entries = grouped_entries.get(selected_group_id, [])
    items: list[MemoryEntryItemViewModel] = []
    for entry in entries:
        items.append(
            MemoryEntryItemViewModel(
                memory_id=str(entry.get("memory_id", "")),
                title=str(entry.get("summary") or entry.get("namespace") or entry.get("memory_id")),
                subtitle=_memory_entry_subtitle(entry),
                is_selected=str(entry.get("memory_id", "")) == selected_entry_id,
            )
        )
    return items


def selected_memory_detail(state: AppState) -> MemoryDetailViewModel:
    if state.memory_request_status == "loading":
        return MemoryDetailViewModel(
            title="Memory Inspector",
            status="loading",
            summary="Loading memory inspection output...",
            content="Waiting for runtime memory data.",
            raw_scope="",
            namespace="",
            provenance="",
            source_run="",
            confidence="",
            created_at="",
            updated_at="",
        )
    if state.memory_request_status == "error":
        return MemoryDetailViewModel(
            title="Memory Inspector",
            status="error",
            summary=state.memory_request_error or "Memory inspection failed.",
            content=state.memory_request_error or "Memory inspection failed.",
            raw_scope="",
            namespace="",
            provenance="",
            source_run="",
            confidence="",
            created_at="",
            updated_at="",
        )

    grouped_entries = _memory_grouped_entries(state)
    selected_group_id = _selected_memory_group_id(state, grouped_entries)
    if not any(grouped_entries.values()):
        return MemoryDetailViewModel(
            title="Memory Inspector",
            status="empty",
            summary="No memory entries available for the current context.",
            content="The runtime returned no memory data for this view.",
            raw_scope="",
            namespace="",
            provenance="",
            source_run="",
            confidence="",
            created_at="",
            updated_at="",
        )
    entries = grouped_entries.get(selected_group_id, [])
    if not entries:
        group_title = _memory_group_title(selected_group_id)
        return MemoryDetailViewModel(
            title=group_title,
            status="empty",
            summary=f"No entries in {group_title.lower()}.",
            content="Select a different memory group to inspect available entries.",
            raw_scope="",
            namespace="",
            provenance="",
            source_run="",
            confidence="",
            created_at="",
            updated_at="",
        )

    selected_entry_id = _selected_memory_entry_id(state, selected_group_id, grouped_entries)
    entry = next(
        (
            candidate
            for candidate in entries
            if str(candidate.get("memory_id", "")) == selected_entry_id
        ),
        entries[0],
    )
    return MemoryDetailViewModel(
        title=str(
            entry.get("summary")
            or entry.get("namespace")
            or entry.get("memory_id")
            or "Memory Entry"
        ),
        status="loaded",
        summary=str(entry.get("summary") or "No summary provided."),
        content=_format_memory_content(entry.get("content")),
        raw_scope=str(entry.get("scope", "")),
        namespace=str(entry.get("namespace", "")),
        provenance=_format_memory_provenance(entry.get("provenance")),
        source_run=str(entry.get("source_run") or "n/a"),
        confidence=_format_memory_confidence(entry.get("confidence")),
        created_at=str(entry.get("created_at", "")),
        updated_at=str(entry.get("updated_at", "")),
    )


def memory_group_summary(state: AppState) -> str:
    grouped_entries = _memory_grouped_entries(state)
    selected_group_id = _selected_memory_group_id(state, grouped_entries)
    entries = grouped_entries.get(selected_group_id, [])
    group = next(
        (item for item in memory_scope_groups(state) if item.group_id == selected_group_id), None
    )
    title = group.title if group is not None else _memory_group_title(selected_group_id)
    description = group.description if group is not None else ""
    context = state.memory_request_context_key or _memory_context_key(state)
    lines = [
        title,
        description,
        f"Entries: {len(entries)}",
        f"Context: {context}",
        "Read-only inspection",
    ]
    return "\n".join(line for line in lines if line)


def config_section_items(state: AppState) -> list[ConfigSectionItemViewModel]:
    selected_section_id = _selected_config_section_id(state)
    items: list[ConfigSectionItemViewModel] = []
    for section_id, title, description, _ in _config_sections(state):
        items.append(
            ConfigSectionItemViewModel(
                section_id=section_id,
                title=title,
                description=description,
                is_selected=section_id == selected_section_id,
            )
        )
    return items


def selected_config_detail(state: AppState) -> ConfigDetailViewModel:
    if state.config_request_status == "loading":
        return ConfigDetailViewModel(
            title="Config Viewer",
            status="loading",
            summary="Loading runtime configuration snapshot...",
            body="Waiting for runtime configuration data.",
        )
    if state.config_request_status == "error":
        message = state.config_request_error or "Configuration request failed."
        return ConfigDetailViewModel(
            title="Config Viewer",
            status="error",
            summary=message,
            body=message,
        )
    if not state.config_snapshot:
        return ConfigDetailViewModel(
            title="Config Viewer",
            status="empty",
            summary="No runtime configuration snapshot available.",
            body="Open the config viewer to request a runtime snapshot.",
        )

    selected_section_id = _selected_config_section_id(state)
    section = next(
        (
            (section_id, title, description, content)
            for section_id, title, description, content in _config_sections(state)
            if section_id == selected_section_id
        ),
        None,
    )
    if section is None:
        return ConfigDetailViewModel(
            title="Config Viewer",
            status="empty",
            summary="No configuration sections are available.",
            body="The runtime snapshot did not produce any operator-facing sections.",
        )
    _, title, description, content = section
    return ConfigDetailViewModel(
        title=title,
        status="loaded",
        summary=description,
        body=content,
    )


def footer_hints(state: AppState) -> _RichText:
    """Return styled footer hints as a Rich Text object.

    Each hint is rendered via key_hint() from theme.typography.
    Hints are separated by three plain spaces.
    """
    from ..theme.typography import key_hint as _key_hint

    def _hints_to_text(hints: list[str]) -> _RichText:
        result = _RichText()
        for index, hint in enumerate(hints):
            parts = hint.split(" ", 1)
            key = parts[0]
            action = parts[1] if len(parts) > 1 else ""
            if index > 0:
                result.append("   ")
            result.append_text(_key_hint(key, action))
        return result

    if state.command_palette_visible:
        return _hints_to_text([
            "Up/Down Move",
            "Enter Run",
            "Esc Close",
            "Q Quit",
        ])
    if state.active_screen == "diagnostics":
        return _hints_to_text([
            "G Palette",
            "N New Task",
            "Up/Down Move",
            "Esc Back",
            "Q Quit",
        ])
    if state.active_screen == "config":
        return _hints_to_text([
            "Up/Down Move",
            "G Palette",
            "N New Task",
            "C Refresh",
            "Esc Back",
            "Q Quit",
        ])
    if state.active_screen == "approvals":
        return _hints_to_text([
            "A Approve",
            "R Reject",
            "Enter Open Task",
            "G Palette",
            "N New Task",
            "C Config",
            "Esc Dashboard",
            "Q Quit",
        ])
    if state.active_screen == "task_detail":
        action_bar = task_action_bar(state)
        hints = [
            "G Palette",
            "N New Task",
            "F Filter Events",
            "/ Search Events",
            "L Toggle Logs",
            "Esc Dashboard",
            "A Approvals",
            "C Config",
            "O Artifacts",
            "D Diagnostics",
            "Q Quit",
        ]
        if state.task_detail_show_logs:
            hints.insert(0, "Up/Down Scroll Logs")
        if action_bar.resume_enabled:
            hints.insert(0, "R Resume")
        return _hints_to_text(hints)
    if state.active_screen == "artifacts":
        return _hints_to_text([
            "G Palette",
            "N New Task",
            "Up/Down Move",
            "Enter Open",
            "E External Open",
            "C Config",
            "T Group Task",
            "R Group Run",
            "Y Group Type",
            "Esc Back",
        ])
    if state.active_screen == "markdown_viewer":
        return _hints_to_text(["Esc Back", "Q Quit"])
    if state.active_screen == "memory":
        return _hints_to_text([
            "G Palette",
            "N New Task",
            "Up/Down Move",
            "Tab Focus",
            "C Config",
            "M Refresh",
            "Esc Back",
            "Q Quit",
        ])
    if state.focused_pane == "approvals":
        return _hints_to_text([
            "G Palette",
            "N New Task",
            "Up/Down Move Approval",
            "Tab Focus",
            "Enter Open Approvals",
            "A Approvals",
            "Q Quit",
        ])
    if state.focused_pane == "summary":
        return _hints_to_text([
            "G Palette",
            "N New Task",
            "Up/Down Scroll Summary",
            "Tab Focus",
            "A Approvals",
            "C Config",
            "Ctrl+R Reconnect",
            "Q Quit",
        ])
    return _hints_to_text([
        "G Palette",
        "N New Task",
        "Up/Down Move",
        "Tab Focus",
        "Enter Open Task",
        "A Approvals",
        "C Config",
        "Ctrl+R Reconnect",
        "Q Quit",
    ])


def dashboard_empty_state(state: AppState) -> str | None:
    if state.connection_status == "error":
        return state.last_error or "Runtime connection failed."
    if not state.task_snapshots:
        return "No tasks available yet. Create or attach to a task to populate the dashboard."
    return None


def _selected_task(state: AppState) -> dict[str, Any] | None:
    if state.selected_task_id is None:
        return None
    return state.task_snapshots.get(state.selected_task_id)


def _selected_approval(state: AppState) -> dict[str, Any] | None:
    approval_id = state.selected_approval_id
    if approval_id is None:
        return None
    for entries in state.approvals_by_task.values():
        for approval in entries:
            if str(approval.get("approval_id", "")) == approval_id:
                return approval
    return None


def _selected_diagnostic(state: AppState) -> dict[str, Any] | None:
    task_key = _selected_task_key(state)
    diagnostic_id = state.selected_diagnostic_id
    if task_key is None or diagnostic_id is None:
        return None
    for diagnostic in state.diagnostics_by_task.get(task_key, []):
        if str(diagnostic.get("diagnostic_id", "")) == diagnostic_id:
            return diagnostic
    return None


def _selected_task_key(state: AppState) -> tuple[str, str] | None:
    task = _selected_task(state)
    if task is None or state.selected_task_id is None:
        return None
    run_id = task.get("run_id")
    if not isinstance(run_id, str):
        return None
    return (state.selected_task_id, run_id)


def _selected_task_events(state: AppState) -> list[TaskEventRecord]:
    task_key = _selected_task_key(state)
    if task_key is None:
        return []
    return list(state.run_event_buffers.get(task_key, []))


def _filtered_task_events(state: AppState) -> list[TaskEventRecord]:
    filter_mode = state.task_timeline_filter.strip().lower() or "all"
    search_query = state.task_timeline_search_query.strip().casefold()
    events: list[TaskEventRecord] = []
    for event in _selected_task_events(state):
        if not _event_matches_filter(event, filter_mode):
            continue
        if search_query and not _event_matches_search(event, search_query):
            continue
        events.append(event)
    return events


def _timeline_event(event: TaskEventRecord) -> TimelineEventViewModel:
    return TimelineEventViewModel(
        timestamp=event.timestamp,
        event_type=event.event_type,
        summary=event.summary,
        severity=event.severity,
        repeat_count=1,
        source_name=event.source_name,
        highlight=_is_priority_event(event.event_type),
        highlight_label=_priority_event_label(event.event_type),
    )


def _should_collapse_timeline_event(event_type: str) -> bool:
    return event_type in {
        "tool.called",
        "tool.rejected",
        "plan.updated",
        "subagent.started",
        "subagent.completed",
    }


def _timeline_filter_label(filter_mode: str) -> str:
    labels = {option.filter_id: option.label for option in timeline_filter_options()}
    return labels.get(filter_mode, "all")


def _event_matches_filter(event: TaskEventRecord, filter_mode: str) -> bool:
    if filter_mode == "all":
        return True
    if filter_mode == "important":
        return event.severity in {"attention", "error", "success"}
    if filter_mode == "tools":
        return event.event_type in {"tool.called", "tool.rejected"}
    if filter_mode == "plans":
        return event.event_type == "plan.updated"
    if filter_mode == "approvals":
        return event.event_type == "approval.requested"
    if filter_mode == "artifacts":
        return event.event_type == "artifact.created"
    if filter_mode == "subagents":
        return event.event_type.startswith("subagent.")
    if filter_mode == "errors":
        return event.severity == "error" or event.event_type in {"task.failed", "tool.rejected"}
    return True


def _event_matches_search(event: TaskEventRecord, search_query: str) -> bool:
    haystack = " ".join(
        [
            event.event_type,
            event.summary,
            event.source_name or "",
            json.dumps(event.payload, sort_keys=True),
        ]
    ).casefold()
    return search_query in haystack


def _matches_command_query(query: str, haystack: str) -> bool:
    if query in haystack:
        return True
    index = 0
    for char in query:
        index = haystack.find(char, index)
        if index == -1:
            return False
        index += 1
    return True


def _command_match_spans(query: str, label: str) -> list[tuple[int, int]]:
    if not query:
        return []
    lowered_query = query.casefold()
    lowered_label = label.casefold()
    if lowered_query in lowered_label:
        start = lowered_label.index(lowered_query)
        return [(start, start + len(query))]
    spans: list[tuple[int, int]] = []
    index = 0
    for char in lowered_query:
        next_index = lowered_label.find(char, index)
        if next_index == -1:
            return []
        spans.append((next_index, next_index + 1))
        index = next_index + 1
    return spans


def _subagent_id(event: TaskEventRecord) -> str | None:
    value = event.payload.get("subagentId")
    if isinstance(value, str) and value.strip():
        return value
    return None


def _artifact_item_view_model(artifact: dict[str, Any]) -> ArtifactItemViewModel:
    return ArtifactItemViewModel(
        artifact_id=str(artifact.get("artifact_id", "")),
        task_id=str(artifact.get("task_id", "")),
        run_id=str(artifact.get("run_id", "")),
        logical_path=str(artifact.get("logical_path", "")),
        display_name=str(
            artifact.get("display_name")
            or artifact.get("logical_path")
            or artifact.get("artifact_id")
            or "artifact"
        ),
        content_type=str(artifact.get("content_type", "unknown")),
        created_at=str(artifact.get("created_at", "")),
        created_at_relative=_relative_time(str(artifact.get("created_at", ""))),
    )


def _all_artifacts(state: AppState) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for entries in state.artifacts_by_task.values():
        artifacts.extend(entries)
    artifacts.sort(
        key=lambda artifact: (
            _artifact_group_label(artifact, state.artifact_group_by),
            _artifact_display_name(artifact),
        ),
    )
    artifacts.sort(
        key=lambda artifact: (
            _artifact_group_label(artifact, state.artifact_group_by),
            str(artifact.get("created_at", "")),
        ),
        reverse=True,
    )
    return artifacts


def _artifact_by_id(state: AppState, artifact_id: str) -> dict[str, Any] | None:
    for artifact in _all_artifacts(state):
        if str(artifact.get("artifact_id", "")) == artifact_id:
            return artifact
    return None


def _memory_entries_for_current_context(state: AppState) -> list[dict[str, Any]]:
    return list(state.memory_entries_by_context.get(_memory_context_key(state), []))


def _config_sections(state: AppState) -> list[tuple[str, str, str, str]]:
    effective_config = state.config_snapshot
    runtime_payload = {
        "runtime": effective_config.get("runtime", {}),
        "transport": effective_config.get("transport", {}),
        "persistence": effective_config.get("persistence", {}),
    }
    sections = [
        (
            "provider_settings",
            "Provider Settings",
            "Runtime, transport, and provider-adjacent settings from the runtime snapshot.",
            _format_config_detail(
                {
                    "settings": runtime_payload,
                    "loaded_profiles": state.config_loaded_profiles,
                }
            ),
        ),
        (
            "sandbox_policy",
            "Sandbox Policy",
            "Runtime policy posture, including any redactions applied to sensitive values.",
            _format_config_detail(
                {
                    "policy": effective_config.get("policy", {}),
                    "redactions": state.config_redactions,
                }
            ),
        ),
        (
            "workspace_context",
            "Workspace Context",
            "Workspace and persistence paths currently exposed by the runtime.",
            _format_config_detail(
                {
                    "cli": effective_config.get("cli", {}),
                    "persistence": effective_config.get("persistence", {}),
                    "config_sources": state.config_sources,
                }
            ),
        ),
        (
            "runtime_identity",
            "Runtime Identity",
            "Identity and provenance information for the active runtime.",
            _format_config_detail(
                {
                    "identity_config": effective_config.get("identity", {}),
                    "runtime_identity": state.runtime_health.get("identity", {}),
                    "runtime_name": state.runtime_health.get("runtime_name"),
                    "protocol_version": state.runtime_health.get("protocol_version"),
                }
            ),
        ),
        (
            "model_routing",
            "Model Routing",
            "Default, primary, and subagent model routing resolved by the runtime.",
            _format_config_detail(
                {
                    "models": effective_config.get("models", {}),
                    "subagents": effective_config.get("subagents", {}),
                }
            ),
        ),
    ]
    return sections


def _memory_context_key(state: AppState) -> str:
    task = _selected_task(state)
    if task is None:
        return "global"
    task_id = str(task.get("task_id") or "")
    run_id = str(task.get("run_id") or "")
    if task_id and run_id:
        return f"{task_id}:{run_id}"
    if task_id:
        return task_id
    return "global"


def _selected_config_section_id(state: AppState) -> str:
    section_ids = [section_id for section_id, *_ in _config_sections(state)]
    if state.selected_config_section_id in section_ids:
        return cast(str, state.selected_config_section_id)
    if section_ids:
        return section_ids[0]
    return "provider_settings"


def _memory_grouped_entries(state: AppState) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {
        "short_term": [],
        "working_context": [],
        "episodic": [],
        "checkpoint_metadata": [],
    }
    for entry in _memory_entries_for_current_context(state):
        scope = str(entry.get("scope", ""))
        if scope == "scratch":
            grouped["short_term"].append(entry)
        elif scope == "run_state":
            grouped["working_context"].append(entry)
        elif scope in {"project", "identity"}:
            grouped["episodic"].append(entry)
        else:
            grouped["episodic"].append(entry)

        if _is_checkpoint_candidate(entry):
            grouped["checkpoint_metadata"].append(_checkpoint_projection(entry))
    return grouped


def _selected_memory_group_id(
    state: AppState, grouped_entries: dict[str, list[dict[str, Any]]]
) -> str:
    if (
        state.selected_memory_group_id in grouped_entries
        and grouped_entries[cast(str, state.selected_memory_group_id)]
    ):
        return cast(str, state.selected_memory_group_id)
    for group_id, entries in grouped_entries.items():
        if entries:
            return group_id
    return "short_term"


def _selected_memory_entry_id(
    state: AppState,
    selected_group_id: str,
    grouped_entries: dict[str, list[dict[str, Any]]],
) -> str | None:
    entries = grouped_entries.get(selected_group_id, [])
    entry_ids = [str(entry.get("memory_id", "")) for entry in entries if entry.get("memory_id")]
    if state.selected_memory_entry_id in entry_ids:
        return state.selected_memory_entry_id
    return entry_ids[0] if entry_ids else None


def _memory_group_title(group_id: str) -> str:
    titles = {
        "short_term": "Short-Term Memory",
        "working_context": "Working Context",
        "episodic": "Episodic Memory",
        "checkpoint_metadata": "Checkpoint Metadata",
    }
    return titles.get(group_id, "Memory")


def _memory_entry_subtitle(entry: dict[str, Any]) -> str:
    bits = [
        str(entry.get("scope", "")),
        str(entry.get("namespace", "")),
        str(entry.get("updated_at", "")),
    ]
    return " | ".join(bit for bit in bits if bit)


def _is_checkpoint_candidate(entry: dict[str, Any]) -> bool:
    scope = str(entry.get("scope", ""))
    if scope not in {"run_state", "scratch"}:
        return False
    provenance = entry.get("provenance")
    return bool(entry.get("source_run")) or (isinstance(provenance, dict) and bool(provenance))


def _checkpoint_projection(entry: dict[str, Any]) -> dict[str, Any]:
    provenance = (
        dict(entry.get("provenance", {})) if isinstance(entry.get("provenance"), dict) else {}
    )
    checkpoint_summary = str(entry.get("summary") or entry.get("memory_id") or "checkpoint")
    checkpoint_content = {
        "memory_id": entry.get("memory_id"),
        "raw_scope": entry.get("scope"),
        "namespace": entry.get("namespace"),
        "source_run": entry.get("source_run"),
        "provenance": provenance,
    }
    return {
        "memory_id": f"checkpoint::{entry.get('memory_id', '')}",
        "scope": entry.get("scope", ""),
        "namespace": entry.get("namespace", ""),
        "summary": f"Checkpoint: {checkpoint_summary}",
        "content": json.dumps(checkpoint_content, indent=2, sort_keys=True),
        "provenance": provenance,
        "source_run": entry.get("source_run"),
        "confidence": entry.get("confidence"),
        "created_at": entry.get("created_at", ""),
        "updated_at": entry.get("updated_at", ""),
    }


def _format_memory_content(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return "No content available."
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return value
        return json.dumps(parsed, indent=2, sort_keys=True)
    if isinstance(value, dict):
        return json.dumps(value, indent=2, sort_keys=True)
    return str(value or "No content available.")


def _format_memory_provenance(value: Any) -> str:
    if isinstance(value, dict):
        if not value:
            return "n/a"
        return json.dumps(value, indent=2, sort_keys=True)
    if value is None:
        return "n/a"
    return str(value)


def _format_memory_confidence(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    if value is None:
        return "n/a"
    return str(value)


def _format_config_detail(value: Any) -> str:
    if isinstance(value, str):
        return value or "n/a"
    if value in (None, {}, []):
        return "n/a"
    return json.dumps(value, indent=2, sort_keys=True)


def _selected_artifact_browser_id(state: AppState) -> str | None:
    if state.artifact_browser_selected_id is not None:
        return state.artifact_browser_selected_id
    artifact = selected_artifact_browser_fallback(state)
    if artifact is None:
        return None
    return str(artifact.get("artifact_id", ""))


def selected_artifact_browser_fallback(state: AppState) -> dict[str, Any] | None:
    artifacts = _all_artifacts(state)
    return artifacts[0] if artifacts else None


def _artifact_group_label(artifact: dict[str, Any], group_by: str) -> str:
    if group_by == "run":
        return f"{artifact.get('task_id', '')}/{artifact.get('run_id', '')}"
    if group_by == "type":
        return str(artifact.get("content_type", "unknown"))
    return str(artifact.get("task_id", ""))


def _artifact_display_name(artifact: dict[str, Any]) -> str:
    return str(
        artifact.get("display_name")
        or artifact.get("logical_path")
        or artifact.get("artifact_id")
        or "artifact"
    )


def _artifact_open_label(
    artifact: dict[str, Any], *, external_open_supported: bool | None = None
) -> str:
    if str(artifact.get("content_type", "")) == "text/markdown":
        return "Open Viewer"
    if external_open_supported is False:
        return "Unavailable"
    return "Open Externally"


def _approval_request_type(approval: dict[str, Any]) -> str:
    value = approval.get("type")
    if isinstance(value, str) and value.strip():
        return value
    return "approval"


def _approval_policy_context(approval: dict[str, Any]) -> str:
    scope = approval.get("scope")
    if not isinstance(scope, dict) or not scope:
        return "unspecified"
    boundary_key = scope.get("boundary_key")
    if isinstance(boundary_key, str) and boundary_key.strip():
        return boundary_key
    kind = scope.get("kind")
    if isinstance(kind, str) and kind.strip():
        return kind
    first_key = next(iter(sorted(scope)))
    return str(first_key)


def _approval_requested_action(approval: dict[str, Any]) -> str:
    scope = approval.get("scope")
    if isinstance(scope, dict):
        for key in ("path_scope", "target_scope", "source_path", "memory_scope"):
            value = scope.get(key)
            if isinstance(value, str) and value.strip():
                return value
    scope_summary = approval.get("scope_summary")
    if isinstance(scope_summary, str) and scope_summary.strip():
        return scope_summary
    return _approval_request_type(approval)


def _actionable_status_label(task: dict[str, Any] | None) -> str:
    if task is None:
        return "Select a task"
    status = str(task.get("status", "unknown")).lower()
    if str(task.get("pause_reason", "")).lower() == "awaiting_user_input":
        return "Reply to task"
    if status in {"paused", "awaiting_approval"}:
        return "Review approval"
    if status == "completed":
        return "Open artifacts"
    if status == "failed":
        return "View diagnostics"
    if status in {"executing", "running", "planning", "accepted"}:
        return "Tail timeline"
    return "Inspect task"


def _actionable_status_hint(task: dict[str, Any] | None) -> str:
    if task is None:
        return "Select a task to inspect its timeline, approvals, and artifacts."
    status = str(task.get("status", "unknown")).lower()
    if str(task.get("pause_reason", "")).lower() == "awaiting_user_input":
        return "Paused for your reply. Type: reply <message>"
    if status in {"paused", "awaiting_approval"}:
        return "Paused. Press A to review approval."
    if status == "completed":
        return "Completed. Press O to open artifacts."
    if status == "failed":
        return "Failed. Press D to view diagnostics."
    if status in {"executing", "running", "planning", "accepted"}:
        return "Running. Press L to toggle logs or / to search the timeline."
    return "Commands: approvals, artifacts, diagnostics, memory, config, help."


def _highlighted_task_ids(state: AppState) -> set[str]:
    return {
        event.task_id
        for event in _selected_task_events(state)[-10:]
        if _is_priority_event(event.event_type)
    }


def _highlighted_approval_ids(state: AppState) -> set[str]:
    approval_ids: set[str] = set()
    for event in _selected_task_events(state)[-10:]:
        if event.event_type != "approval.requested":
            continue
        approval = event.payload.get("approval")
        if isinstance(approval, dict):
            approval_id = approval.get("approval_id")
            if isinstance(approval_id, str) and approval_id:
                approval_ids.add(approval_id)
    return approval_ids


def _highlighted_artifact_ids(state: AppState) -> set[str]:
    artifact_ids: set[str] = set()
    for event in _selected_task_events(state)[-10:]:
        if event.event_type != "artifact.created":
            continue
        artifact = event.payload.get("artifact")
        if isinstance(artifact, dict):
            artifact_id = artifact.get("artifact_id")
            if isinstance(artifact_id, str) and artifact_id:
                artifact_ids.add(artifact_id)
    return artifact_ids


def _is_priority_event(event_type: str) -> bool:
    return event_type in {
        "approval.requested",
        "artifact.created",
        "task.failed",
        "task.completed",
        "task.started",
        "task.resumed",
    }


def _priority_event_label(event_type: str) -> str | None:
    labels = {
        "approval.requested": "APPROVAL",
        "artifact.created": "ARTIFACT",
        "task.failed": "FAILED",
        "task.completed": "DONE",
        "task.started": "STARTED",
        "task.resumed": "RESUMED",
    }
    return labels.get(event_type)


def _sorted_task_snapshots(state: AppState) -> list[dict[str, Any]]:
    tasks = cast(list[dict[str, Any]], list(state.task_snapshots.values()))
    tasks.sort(
        key=lambda task: (
            str(task.get("last_event_at") or task.get("updated_at") or ""),
            str(task.get("updated_at") or ""),
            str(task.get("created_at") or ""),
        ),
        reverse=True,
    )
    return tasks


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    return 0


def _str_or_none(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
