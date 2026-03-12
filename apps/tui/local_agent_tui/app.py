from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from .actions.approve_request import build_approval_request_action
from .actions.inspect_memory import build_inspect_memory_action
from .actions.open_artifact import build_open_artifact_action
from .protocol.event_stream import consume_task_stream
from .protocol.protocol_client import ProtocolClient, ProtocolClientError
from .screens.approvals import ApprovalsScreen
from .screens.artifacts import ArtifactsScreen
from .screens.command_palette import CommandPaletteScreen
from .screens.config import ConfigScreen
from .screens.create_task import CreateTaskScreen
from .screens.dashboard import DashboardScreen
from .screens.diagnostics import DiagnosticsScreen
from .screens.markdown_viewer import MarkdownViewerScreen
from .screens.memory import MemoryScreen
from .screens.task_detail import TaskDetailScreen
from .store.app_state import AppStateStore, UiMessage
from .store.selectors import (
    artifact_browser_rows,
    command_palette,
    config_section_items,
    diagnostics_items,
    memory_entry_items,
    memory_scope_groups,
    pending_approvals,
    selected_artifact_browser_item,
    selected_approval_detail,
    selected_artifact_preview,
    selected_memory_detail,
    recent_task_ids,
    task_artifact_panel,
    task_action_bar,
)
from .widgets.status_bar import StatusBar

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.css.query import NoMatches
else:  # pragma: no cover
    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.css.query import NoMatches
    except ModuleNotFoundError as exc:
        App = cast(Any, object)
        ComposeResult = cast(Any, object)
        Binding = cast(Any, object)
        NoMatches = cast(Any, RuntimeError)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


def ensure_textual_available() -> None:
    if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
        raise RuntimeError("textual is required to run the TUI") from _TEXTUAL_IMPORT_ERROR


@dataclass(slots=True)
class BootstrapConfig:
    config_path: str
    task_id: str | None = None
    run_id: str | None = None


class AgentTUI(App):  # type: ignore[misc]
    CSS_PATH = "theme/styles.tcss"
    TITLE = "Local Agent Harness"
    SUB_TITLE = "Operator Console"
    BINDINGS = [
        Binding("up", "move_up", "Up", show=False, priority=True),
        Binding("k", "move_up", "Up", show=False, priority=True),
        Binding("down", "move_down", "Down", show=False, priority=True),
        Binding("j", "move_down", "Down", show=False, priority=True),
        Binding("g", "open_command_palette", "Palette", show=False),
        Binding("n", "create_task", "New Task", show=False),
        Binding("tab", "focus_next_pane", "Next Pane", show=False, priority=True),
        Binding("shift+tab", "focus_prev_pane", "Prev Pane", show=False, priority=True),
        Binding("enter", "open_task", "Open Task", show=False, priority=True),
        Binding("a", "open_approvals", "Approvals", show=False, priority=True),
        Binding("c", "open_config", "Config", show=False),
        Binding("m", "open_memory", "Memory", show=False, priority=True),
        Binding("r", "resume_task", "Resume", show=False, priority=True),
        Binding("o", "open_artifacts", "Artifacts", show=False, priority=True),
        Binding("t", "group_artifacts_task", "Task Group", show=False, priority=True),
        Binding("y", "group_artifacts_type", "Type Group", show=False, priority=True),
        Binding("escape", "back_dashboard", "Dashboard", show=False, priority=True),
        Binding("q", "quit", "Quit", show=False, priority=True),
    ]

    def __init__(self, *, config_path: str, task_id: str | None, run_id: str | None) -> None:
        ensure_textual_available()
        super().__init__()
        self._bootstrap = BootstrapConfig(config_path=config_path, task_id=task_id, run_id=run_id)
        self._client = ProtocolClient(config_path)
        self._store = AppStateStore()
        self._status_bar = StatusBar(id="status-bar")
        self._stream_key: tuple[str, str] | None = None
        self._render_interval = 1 / 30
        self._render_scheduled = False
        self._last_render_at = 0.0
        self.install_screen(DashboardScreen(), name="dashboard")
        self.install_screen(TaskDetailScreen(), name="task_detail")
        self.install_screen(ApprovalsScreen(), name="approvals")
        self.install_screen(ArtifactsScreen(), name="artifacts")
        self.install_screen(MarkdownViewerScreen(), name="markdown_viewer")
        self.install_screen(MemoryScreen(), name="memory")
        self.install_screen(ConfigScreen(), name="config")
        self.install_screen(DiagnosticsScreen(), name="diagnostics")
        self.install_screen(CommandPaletteScreen(), name="command_palette")
        self.install_screen(CreateTaskScreen(), name="create_task")

    def compose(self) -> ComposeResult:
        yield self._status_bar

    async def on_mount(self) -> None:
        self.push_screen("dashboard")
        self._store.dispatch({"kind": "connection", "status": "connecting"})
        self._render_state()
        self.run_worker(self._connect_and_refresh(), group="runtime-bootstrap", exclusive=True)

    async def on_unmount(self) -> None:
        await self._client.close()

    async def _connect_and_refresh(self) -> None:
        try:
            await self._client.connect()
            self._store.dispatch({"kind": "connection", "status": "connected"})
            health = await self._client.runtime_health()
            self._store.dispatch({"kind": "rpc", "name": "runtime.health", "payload": health})
            task_list = await self._client.task_list(limit=10)
            self._store.dispatch({"kind": "rpc", "name": "task.list", "payload": task_list})
            if self._bootstrap.task_id is not None:
                self._store.dispatch(
                    {
                        "kind": "ui",
                        "selected_task_id": self._bootstrap.task_id,
                        "active_screen": "dashboard",
                    }
                )
                task = await self._client.task_get(self._bootstrap.task_id, self._bootstrap.run_id)
                self._store.dispatch({"kind": "rpc", "name": "task.get", "payload": task})
            await self._prefetch_dashboard_data()
            await self._prime_config_snapshot()
            self._render_state()
            await self._sync_selected_task()
        except ProtocolClientError as exc:
            self._store.dispatch({"kind": "connection", "status": "error", "error": str(exc)})
            self._render_state()

    async def _prefetch_dashboard_data(self) -> None:
        state = self._store.snapshot()
        for task_id in recent_task_ids(state):
            task = state.task_snapshots.get(task_id)
            if task is None:
                continue
            run_id = str(task.get("run_id", "")) or None
            await self._load_task_related(task_id=task_id, run_id=run_id)

    async def _refresh_known_artifacts(self) -> None:
        state = self._store.snapshot()
        for task_id in recent_task_ids(state):
            task = state.task_snapshots.get(task_id)
            if task is None:
                continue
            run_id = str(task.get("run_id", "")) or None
            artifacts = await self._client.task_artifacts_list(task_id, run_id)
            self._store.dispatch(
                {"kind": "rpc", "name": "task.artifacts.list", "payload": artifacts}
            )
        self._ensure_artifact_browser_selection()
        self._render_state()
        self._queue_selected_artifact_preview_load()

    async def _refresh_known_approvals(self) -> None:
        state = self._store.snapshot()
        for task_id in recent_task_ids(state):
            task = state.task_snapshots.get(task_id)
            if task is None:
                continue
            run_id = str(task.get("run_id", "")) or None
            approvals = await self._client.task_approvals_list(task_id, run_id)
            self._store.dispatch(
                {"kind": "rpc", "name": "task.approvals.list", "payload": approvals}
            )
        self._render_state()

    async def _load_task_related(self, *, task_id: str, run_id: str | None) -> None:
        approvals = await self._client.task_approvals_list(task_id, run_id)
        self._store.dispatch({"kind": "rpc", "name": "task.approvals.list", "payload": approvals})
        artifacts = await self._client.task_artifacts_list(task_id, run_id)
        self._store.dispatch({"kind": "rpc", "name": "task.artifacts.list", "payload": artifacts})

    async def _sync_selected_task(self) -> None:
        state = self._store.snapshot()
        if state.selected_task_id is None:
            self._render_state()
            return
        task = state.task_snapshots.get(state.selected_task_id)
        run_id = str(task.get("run_id", "")) if task else self._bootstrap.run_id
        task_payload = await self._client.task_get(state.selected_task_id, run_id or None)
        self._store.dispatch({"kind": "rpc", "name": "task.get", "payload": task_payload})
        await self._load_task_related(task_id=state.selected_task_id, run_id=run_id or None)
        self._render_state()
        self._start_selected_task_stream(task_id=state.selected_task_id, run_id=run_id or None)

    def _start_selected_task_stream(self, *, task_id: str, run_id: str | None) -> None:
        stream_key = (task_id, run_id or "")
        if self._stream_key == stream_key:
            return
        self._stream_key = stream_key
        self.run_worker(
            self._stream_selected_task(task_id=task_id, run_id=run_id),
            group="task-stream",
            exclusive=True,
        )

    async def _stream_selected_task(self, *, task_id: str, run_id: str | None) -> None:
        try:
            await consume_task_stream(
                self._client,
                task_id=task_id,
                run_id=run_id,
                dispatch=self._dispatch_and_render,
            )
        except ProtocolClientError as exc:
            self._store.dispatch({"kind": "connection", "status": "error", "error": str(exc)})
            self._render_state()
        finally:
            if self._stream_key == (task_id, run_id or ""):
                self._stream_key = None

    def _dispatch_and_render(self, message: dict[str, Any]) -> None:
        self._store.dispatch(message)  # type: ignore[arg-type]
        if getattr(self, "_thread_id", None) == threading.get_ident():
            self._request_render()
            return
        self.call_from_thread(self._request_render)

    def _request_render(self) -> None:
        now = time.monotonic()
        if now - self._last_render_at >= self._render_interval and not self._render_scheduled:
            self._render_state()
            return
        if self._render_scheduled:
            return
        self._render_scheduled = True
        delay = max(0.0, self._render_interval - (now - self._last_render_at))
        self.set_timer(delay, self._flush_scheduled_render)

    def _flush_scheduled_render(self) -> None:
        self._render_scheduled = False
        self._render_state()

    def _render_state(self) -> None:
        self._last_render_at = time.monotonic()
        state = self._store.snapshot()
        self._status_bar.update_from_state(state)
        screen = self.screen
        update_from_state = getattr(screen, "update_from_state", None)
        if callable(update_from_state):
            try:
                update_from_state(state)
            except NoMatches:
                return

    def handle_dashboard_task_selected(self, task_id: str) -> None:
        state = self._store.snapshot()
        if state.selected_task_id == task_id:
            return
        self._store.dispatch({"kind": "ui", "selected_task_id": task_id})
        self._render_state()
        self.run_worker(self._sync_selected_task(), group="selection-sync", exclusive=True)

    def _set_active_screen(self, screen_name: str) -> None:
        message: UiMessage = {"kind": "ui", "active_screen": screen_name}
        if screen_name != "approvals":
            message["approval_feedback"] = None
        self._store.dispatch(message)
        self.switch_screen(screen_name)
        self._render_state()

    def action_move_up(self) -> None:
        if self._store.snapshot().command_palette_visible:
            self.move_command_palette_selection(-1)
            return
        if self._store.snapshot().active_screen == "markdown_viewer":
            action = getattr(self.screen, "action_scroll_up", None)
            if callable(action):
                action()
            return
        self._move_focused_selection(-1)

    def action_move_down(self) -> None:
        if self._store.snapshot().command_palette_visible:
            self.move_command_palette_selection(1)
            return
        if self._store.snapshot().active_screen == "markdown_viewer":
            action = getattr(self.screen, "action_scroll_down", None)
            if callable(action):
                action()
            return
        self._move_focused_selection(1)

    def _move_focused_selection(self, delta: int) -> None:
        state = self._store.snapshot()
        if state.active_screen == "memory":
            self._move_memory_selection(delta)
            return
        if state.active_screen == "config":
            self._move_config_selection(delta)
            return
        if state.active_screen == "artifacts":
            self._move_artifact_browser_selection(delta)
            return
        if state.active_screen == "diagnostics":
            self._move_diagnostic_selection(delta)
            return
        if state.active_screen == "approvals":
            self._move_approval_selection(delta)
            return
        if state.active_screen == "dashboard" and state.focused_pane == "approvals":
            self._move_approval_selection(delta)
            return
        self._move_selection(delta)

    def _move_selection(self, delta: int) -> None:
        state = self._store.snapshot()
        task_ids = recent_task_ids(state)
        if not task_ids:
            return
        if state.selected_task_id not in task_ids:
            self.handle_dashboard_task_selected(task_ids[0])
            return
        current_index = task_ids.index(state.selected_task_id)
        next_index = max(0, min(len(task_ids) - 1, current_index + delta))
        self.handle_dashboard_task_selected(task_ids[next_index])

    def action_focus_next_pane(self) -> None:
        self._cycle_focus(1)

    def action_focus_prev_pane(self) -> None:
        self._cycle_focus(-1)

    def _cycle_focus(self, delta: int) -> None:
        panes = ["tasks", "approvals", "artifacts"]
        state = self._store.snapshot()
        if state.active_screen == "memory":
            panes = ["memory_groups", "memory_entries"]
        elif state.active_screen == "config":
            panes = ["config_sections"]
        current_index = panes.index(state.focused_pane) if state.focused_pane in panes else 0
        next_index = (current_index + delta) % len(panes)
        self._store.dispatch({"kind": "ui", "focused_pane": panes[next_index]})
        self._render_state()

    def action_open_task(self) -> None:
        state = self._store.snapshot()
        if state.command_palette_visible:
            self.action_run_palette_command()
            return
        if state.active_screen == "artifacts":
            self._open_selected_artifact()
            return
        if state.active_screen == "markdown_viewer":
            return
        if state.active_screen == "approvals":
            self.action_open_selected_approval_task()
            return
        if state.active_screen == "diagnostics":
            return
        if state.active_screen == "dashboard" and state.focused_pane == "approvals":
            self._set_active_screen("approvals")
            return
        if state.selected_task_id is None:
            return
        self._set_active_screen("task_detail")

    def action_open_approvals(self) -> None:
        state = self._store.snapshot()
        if state.active_screen == "approvals":
            self.action_approve_selected_request()
            return
        self._set_active_screen("approvals")
        self.run_worker(
            self._refresh_known_approvals(),
            group="approvals-refresh",
            exclusive=True,
        )

    def action_open_memory(self) -> None:
        self._open_memory_inspector()

    def action_open_config(self) -> None:
        if self.screen.__class__.__name__ == "ConfigScreen":
            self.run_worker(self._refresh_config(), group="config-refresh", exclusive=True)
            return
        self._open_config_viewer()

    def action_open_command_palette(self) -> None:
        state = self._store.snapshot()
        if self.screen.__class__.__name__ == "CreateTaskScreen":
            return
        if state.active_screen == "markdown_viewer":
            return
        if state.command_palette_visible:
            self.close_command_palette()
            return
        self._store.dispatch(
            {
                "kind": "ui",
                "command_palette_visible": True,
                "command_palette_query": "",
                "command_palette_selected_id": None,
            }
        )
        self.push_screen("command_palette")
        self._render_state()

    def action_create_task(self) -> None:
        self.open_create_task()

    def action_run_palette_command(self) -> None:
        self.run_selected_palette_command()

    def action_resume_task(self) -> None:
        state = self._store.snapshot()
        if state.active_screen == "artifacts":
            self._set_artifact_group("run")
            return
        if state.active_screen == "approvals":
            self.action_reject_selected_request()
            return
        if state.active_screen != "task_detail" or state.selected_task_id is None:
            return
        actions = task_action_bar(state)
        if not actions.resume_enabled:
            return
        task = state.task_snapshots.get(state.selected_task_id)
        if task is None:
            return
        run_id = str(task.get("run_id", "")) or None
        self.run_worker(
            self._resume_selected_task(task_id=state.selected_task_id, run_id=run_id),
            group="task-resume",
            exclusive=True,
        )

    async def _resume_selected_task(self, *, task_id: str, run_id: str | None) -> None:
        try:
            response = await self._client.task_resume(task_id, run_id)
            self._store.dispatch({"kind": "rpc", "name": "task.resume", "payload": response})
            self._render_state()
            self._start_selected_task_stream(task_id=task_id, run_id=run_id)
        except ProtocolClientError as exc:
            self._store.dispatch({"kind": "connection", "status": "error", "error": str(exc)})
            self._render_state()

    def action_open_artifacts(self) -> None:
        state = self._store.snapshot()
        if state.active_screen == "artifacts":
            self._open_selected_artifact()
            return
        origin_screen = state.active_screen
        message: UiMessage = {
            "kind": "ui",
            "active_screen": "artifacts",
            "artifact_browser_origin_screen": origin_screen,
        }
        if state.active_screen == "task_detail":
            selected_panel = next(
                (artifact for artifact in task_artifact_panel(state) if artifact.is_selected),
                None,
            )
            if selected_panel is not None:
                message["artifact_browser_selected_id"] = selected_panel.artifact_id
        self._store.dispatch(message)
        self.switch_screen("artifacts")
        self._ensure_artifact_browser_selection()
        self._render_state()
        self.run_worker(self._refresh_known_artifacts(), group="artifacts-refresh", exclusive=True)
        self._queue_selected_artifact_preview_load()

    def action_group_artifacts_task(self) -> None:
        self._set_artifact_group("task")

    def action_group_artifacts_type(self) -> None:
        self._set_artifact_group("type")

    def action_back_dashboard(self) -> None:
        state = self._store.snapshot()
        if state.command_palette_visible:
            self.close_command_palette()
            return
        if state.active_screen == "artifacts":
            self._set_active_screen(state.artifact_browser_origin_screen or "dashboard")
            return
        if state.active_screen == "markdown_viewer":
            self._set_active_screen("artifacts")
            return
        if state.active_screen == "memory":
            self._set_active_screen(state.memory_origin_screen or "dashboard")
            return
        if state.active_screen == "config":
            self._set_active_screen(state.config_origin_screen or "dashboard")
            return
        if state.active_screen == "diagnostics":
            self._set_active_screen(state.diagnostics_origin_screen or "dashboard")
            return
        self._set_active_screen("dashboard")

    async def action_quit(self) -> None:
        if self._store.snapshot().active_screen == "markdown_viewer":
            self.action_back_dashboard()
            return
        self.exit()

    def action_open_selected_approval_task(self) -> None:
        selected = selected_approval_detail(self._store.snapshot())
        if selected is None:
            return
        self._store.dispatch(
            {
                "kind": "ui",
                "selected_task_id": selected.task_id,
                "focused_pane": "tasks",
                "approval_feedback": None,
            }
        )
        self._set_active_screen("task_detail")
        self.run_worker(self._sync_selected_task(), group="selection-sync", exclusive=True)

    def handle_artifact_browser_selected(self, artifact_id: str) -> None:
        state = self._store.snapshot()
        if state.artifact_browser_selected_id == artifact_id:
            return
        self._store.dispatch({"kind": "ui", "artifact_browser_selected_id": artifact_id})
        self._render_state()
        self._queue_selected_artifact_preview_load()

    def _move_approval_selection(self, delta: int) -> None:
        state = self._store.snapshot()
        approvals = pending_approvals(state)
        if not approvals:
            return
        approval_ids = [approval.approval_id for approval in approvals]
        current_id = state.selected_approval_id
        if current_id not in approval_ids:
            next_id = approval_ids[0]
        else:
            current_index = approval_ids.index(current_id)
            next_index = max(0, min(len(approval_ids) - 1, current_index + delta))
            next_id = approval_ids[next_index]
        self._store.dispatch({"kind": "ui", "selected_approval_id": next_id})
        self._render_state()

    def _move_diagnostic_selection(self, delta: int) -> None:
        items = diagnostics_items(self._store.snapshot())
        if not items:
            return
        current_index = next((index for index, item in enumerate(items) if item.is_selected), -1)
        next_item = items[(current_index + delta) % len(items)]
        self._store.dispatch({"kind": "ui", "selected_diagnostic_id": next_item.diagnostic_id})
        self._render_state()

    def move_command_palette_selection(self, delta: int) -> None:
        items = command_palette(self._store.snapshot()).items
        if not items:
            return
        current_index = next((index for index, item in enumerate(items) if item.is_selected), -1)
        next_item = items[(current_index + delta) % len(items)]
        self._store.dispatch({"kind": "ui", "command_palette_selected_id": next_item.command_id})
        self._render_state()

    def handle_command_palette_query_changed(self, query: str) -> None:
        selected_id = None
        self._store.dispatch(
            {
                "kind": "ui",
                "command_palette_query": query,
                "command_palette_selected_id": selected_id,
            }
        )
        items = command_palette(self._store.snapshot()).items
        if items:
            self._store.dispatch({"kind": "ui", "command_palette_selected_id": items[0].command_id})
        self._render_state()

    def run_selected_palette_command(self) -> None:
        state = self._store.snapshot()
        items = command_palette(state).items
        selected = next((item for item in items if item.is_selected), None)
        if selected is None:
            return
        self.close_command_palette()
        commands = {
            "create_task": self.open_create_task,
            "resume_task": self.action_resume_task,
            "open_approvals": self.action_open_approvals,
            "open_artifacts": self.action_open_artifacts,
            "open_memory": self.action_open_memory,
            "open_config": self.action_open_config,
            "open_diagnostics": self.action_open_diagnostics,
        }
        handler = commands.get(selected.command_id)
        if handler is not None:
            handler()

    def close_command_palette(self) -> None:
        if not self._store.snapshot().command_palette_visible:
            return
        self._store.dispatch(
            {
                "kind": "ui",
                "command_palette_visible": False,
                "command_palette_query": "",
                "command_palette_selected_id": None,
            }
        )
        self.pop_screen()
        self._render_state()

    def action_approve_selected_request(self) -> None:
        self._submit_selected_approval("approve")

    def action_reject_selected_request(self) -> None:
        self._submit_selected_approval("reject")

    def _submit_selected_approval(self, decision: str) -> None:
        state = self._store.snapshot()
        if state.active_screen != "approvals":
            return
        selected = selected_approval_detail(state)
        if selected is None:
            return
        action = build_approval_request_action(
            task_id=selected.task_id,
            run_id=selected.run_id,
            approval_id=selected.approval_id,
            decision=decision,  # type: ignore[arg-type]
        )
        self.run_worker(
            self._decide_selected_approval(
                action.task_id,
                action.run_id,
                action.approval_id,
                action.decision,
            ),
            group="approval-decision",
            exclusive=True,
        )

    async def _decide_selected_approval(
        self,
        task_id: str,
        run_id: str,
        approval_id: str,
        decision: str,
    ) -> None:
        try:
            response = await self._client.task_approve(
                task_id,
                run_id or None,
                approval_id,
                decision,
            )
            self._store.dispatch({"kind": "rpc", "name": "task.approve", "payload": response})
            await self._load_task_related(task_id=task_id, run_id=run_id or None)
            feedback = f"{decision.title()} {approval_id}."
            self._store.dispatch({"kind": "ui", "approval_feedback": feedback})
            self._render_state()
            self._start_selected_task_stream(task_id=task_id, run_id=run_id or None)
        except ProtocolClientError as exc:
            self._store.dispatch(
                {
                    "kind": "ui",
                    "approval_feedback": f"Approval request failed: {exc}",
                }
            )
            self._render_state()

    def _move_artifact_browser_selection(self, delta: int) -> None:
        rows = artifact_browser_rows(self._store.snapshot())
        if not rows:
            return
        current_index = next((index for index, row in enumerate(rows) if row.is_selected), -1)
        next_row = rows[(current_index + delta) % len(rows)]
        self.handle_artifact_browser_selected(next_row.artifact_id)

    def _move_memory_selection(self, delta: int) -> None:
        state = self._store.snapshot()
        if state.focused_pane == "memory_entries":
            entries = memory_entry_items(state)
            if not entries:
                return
            current_index = next(
                (index for index, item in enumerate(entries) if item.is_selected), -1
            )
            next_item = entries[(current_index + delta) % len(entries)]
            self.handle_memory_entry_selected(next_item.memory_id)
            return
        groups = memory_scope_groups(state)
        if not groups:
            return
        current_index = next((index for index, item in enumerate(groups) if item.is_selected), -1)
        next_group = groups[(current_index + delta) % len(groups)]
        self.handle_memory_group_selected(next_group.group_id)

    def _move_config_selection(self, delta: int) -> None:
        sections = config_section_items(self._store.snapshot())
        if not sections:
            return
        current_index = next((index for index, item in enumerate(sections) if item.is_selected), -1)
        next_section = sections[(current_index + delta) % len(sections)]
        self.handle_config_section_selected(next_section.section_id)

    def handle_memory_group_selected(self, group_id: str) -> None:
        groups = memory_scope_groups(self._store.snapshot())
        if not any(group.group_id == group_id for group in groups):
            return
        self._store.dispatch(
            {
                "kind": "ui",
                "selected_memory_group_id": group_id,
                "selected_memory_entry_id": None,
            }
        )
        self._ensure_memory_selection()
        self._render_state()

    def handle_memory_entry_selected(self, memory_id: str) -> None:
        entries = memory_entry_items(self._store.snapshot())
        if not any(entry.memory_id == memory_id for entry in entries):
            return
        self._store.dispatch({"kind": "ui", "selected_memory_entry_id": memory_id})
        self._render_state()

    def handle_config_section_selected(self, section_id: str) -> None:
        sections = config_section_items(self._store.snapshot())
        if not any(section.section_id == section_id for section in sections):
            return
        self._store.dispatch({"kind": "ui", "selected_config_section_id": section_id})
        self._render_state()

    def _ensure_artifact_browser_selection(self) -> None:
        state = self._store.snapshot()
        if state.artifact_browser_selected_id is not None:
            return
        fallback = selected_artifact_browser_item(state)
        if fallback is None:
            rows = artifact_browser_rows(state)
            if not rows:
                return
            artifact_id = rows[0].artifact_id
        else:
            artifact_id = str(fallback.get("artifact_id", ""))
        if artifact_id:
            self._store.dispatch({"kind": "ui", "artifact_browser_selected_id": artifact_id})

    def _queue_selected_artifact_preview_load(self) -> None:
        selected = selected_artifact_browser_item(self._store.snapshot())
        if selected is None:
            return
        artifact_id = str(selected.get("artifact_id", ""))
        state = self._store.snapshot()
        if state.artifact_preview_status_by_artifact.get(artifact_id) == "loading":
            return
        if artifact_id in state.artifact_preview_cache:
            return
        self._store.dispatch(
            {
                "kind": "ui",
                "artifact_preview_artifact_id": artifact_id,
                "artifact_preview_status": "loading",
                "artifact_preview_error": None,
            }
        )
        self._render_state()
        self.run_worker(
            self._load_artifact_preview(
                task_id=str(selected.get("task_id", "")),
                run_id=str(selected.get("run_id", "")) or None,
                artifact_id=artifact_id,
            ),
            group=f"artifact-preview-{artifact_id}",
            exclusive=True,
        )

    async def _load_artifact_preview(
        self,
        *,
        task_id: str,
        run_id: str | None,
        artifact_id: str,
    ) -> None:
        try:
            payload = await self._client.task_artifact_get(task_id, artifact_id, run_id)
            self._store.dispatch({"kind": "rpc", "name": "task.artifact.get", "payload": payload})
        except ProtocolClientError as exc:
            self._store.dispatch(
                {
                    "kind": "ui",
                    "artifact_preview_artifact_id": artifact_id,
                    "artifact_preview_status": "failed",
                    "artifact_preview_error": str(exc),
                }
            )
        self._render_state()

    def _open_selected_artifact(self) -> None:
        state = self._store.snapshot()
        selected = selected_artifact_browser_item(state)
        if selected is None:
            return
        artifact_id = str(selected.get("artifact_id", ""))
        preview_model = selected_artifact_preview(state)
        action = build_open_artifact_action(
            artifact_id=artifact_id,
            task_id=str(selected.get("task_id", "")),
            run_id=str(selected.get("run_id", "")),
            content_type=str(selected.get("content_type", "unknown")),
            external_open_supported=preview_model.external_open_supported,
        )
        if action.destination == "markdown_viewer":
            preview_status = state.artifact_preview_status_by_artifact.get(artifact_id, "idle")
            if preview_status == "idle" and artifact_id not in state.artifact_preview_cache:
                self._queue_selected_artifact_preview_load()
            self._store.dispatch(
                {
                    "kind": "ui",
                    "active_screen": "markdown_viewer",
                    "markdown_viewer_artifact_id": artifact_id,
                }
            )
            self.switch_screen("markdown_viewer")
            self._render_state()

    def _set_artifact_group(self, group_by: str) -> None:
        state = self._store.snapshot()
        if state.active_screen != "artifacts":
            return
        self._store.dispatch({"kind": "ui", "artifact_group_by": group_by})
        self._render_state()

    def _open_memory_inspector(self) -> None:
        state = self._store.snapshot()
        task = state.task_snapshots.get(state.selected_task_id) if state.selected_task_id else None
        origin_screen = (
            state.memory_origin_screen if state.active_screen == "memory" else state.active_screen
        )
        action = build_inspect_memory_action(
            task_id=state.selected_task_id,
            run_id=str(task.get("run_id", "")) or None if task is not None else None,
            origin_screen=origin_screen,
        )
        self._store.dispatch(
            {
                "kind": "ui",
                "active_screen": "memory",
                "focused_pane": "memory_groups",
                "memory_origin_screen": action.origin_screen,
            }
        )
        if state.active_screen != "memory":
            self.switch_screen("memory")
        self._render_state()
        self.run_worker(
            self._refresh_memory_inspection(task_id=action.task_id, run_id=action.run_id),
            group="memory-refresh",
            exclusive=True,
        )

    def _open_config_viewer(self) -> None:
        state = self._store.snapshot()
        is_config_screen = self.screen.__class__.__name__ == "ConfigScreen"
        origin_screen = state.config_origin_screen if is_config_screen else state.active_screen
        self._store.dispatch(
            {
                "kind": "ui",
                "active_screen": "config",
                "focused_pane": "config_sections",
                "config_origin_screen": origin_screen,
            }
        )
        if not is_config_screen:
            self.switch_screen("config")
        self._render_state()
        if is_config_screen or not state.config_snapshot:
            self.run_worker(self._refresh_config(), group="config-refresh", exclusive=True)

    def action_open_diagnostics(self) -> None:
        state = self._store.snapshot()
        selected_task_id = state.selected_task_id
        task = state.task_snapshots.get(selected_task_id) if selected_task_id else None
        if task is None or selected_task_id is None:
            return
        origin_screen = (
            state.diagnostics_origin_screen
            if state.active_screen == "diagnostics"
            else state.active_screen
        )
        self._store.dispatch(
            {
                "kind": "ui",
                "active_screen": "diagnostics",
                "diagnostics_origin_screen": origin_screen,
            }
        )
        if state.active_screen != "diagnostics":
            self.switch_screen("diagnostics")
        self._render_state()
        self.run_worker(
            self._refresh_diagnostics(
                task_id=selected_task_id,
                run_id=str(task.get("run_id", "")) or None,
            ),
            group="diagnostics-refresh",
            exclusive=True,
        )

    def open_create_task(self) -> None:
        if self.screen.__class__.__name__ == "CreateTaskScreen":
            return
        if self._store.snapshot().command_palette_visible:
            self.close_command_palette()
        self.push_screen("create_task")

    def close_create_task(self) -> None:
        if self.screen.__class__.__name__ != "CreateTaskScreen":
            return
        self.pop_screen()
        self._render_state()

    def submit_create_task(self, objective: str) -> None:
        text = objective.strip()
        if not text:
            if self.screen.__class__.__name__ == "CreateTaskScreen":
                self.screen.set_status("Objective is required.")  # type: ignore[attr-defined]
            return
        if self.screen.__class__.__name__ == "CreateTaskScreen":
            self.screen.set_status("Creating task...")  # type: ignore[attr-defined]
        self.run_worker(
            self._create_task(objective=text),
            group="create-task",
            exclusive=True,
        )

    async def _refresh_config(self) -> None:
        self._store.dispatch(
            {
                "kind": "ui",
                "config_request_status": "loading",
                "config_request_error": None,
            }
        )
        self._render_state()
        try:
            payload = await self._client.get_config()
            self._store.dispatch({"kind": "rpc", "name": "config.get", "payload": payload})
            self._ensure_config_selection()
        except ProtocolClientError as exc:
            self._store.dispatch(
                {
                    "kind": "ui",
                    "config_request_status": "error",
                    "config_request_error": str(exc),
                }
            )
        self._render_state()

    async def _refresh_diagnostics(self, *, task_id: str, run_id: str | None) -> None:
        self._store.dispatch(
            {
                "kind": "ui",
                "diagnostics_request_status": "loading",
                "diagnostics_request_error": None,
            }
        )
        self._render_state()
        try:
            payload = await self._client.task_diagnostics_list(task_id, run_id)
            payload = {
                **payload,
                "context": {
                    "task_id": task_id,
                    "run_id": run_id,
                },
            }
            self._store.dispatch(
                {"kind": "rpc", "name": "task.diagnostics.list", "payload": payload}
            )
            self._ensure_diagnostic_selection()
        except ProtocolClientError as exc:
            self._store.dispatch(
                {
                    "kind": "ui",
                    "diagnostics_request_status": "error",
                    "diagnostics_request_error": str(exc),
                }
            )
        self._render_state()

    async def _create_task(self, *, objective: str) -> None:
        try:
            state = self._store.snapshot()
            workspace_root = _default_workspace_root(state.config_snapshot) or os.getcwd()
            payload = await self._client.task_create(
                objective=objective,
                workspace_roots=[workspace_root],
            )
            self._store.dispatch({"kind": "rpc", "name": "task.create", "payload": payload})
            task_id = str(payload.get("result", {}).get("task_id", ""))
            run_id = str(payload.get("result", {}).get("run_id", "")) or None
            task_payload = await self._client.task_get(task_id, run_id)
            self._store.dispatch({"kind": "rpc", "name": "task.get", "payload": task_payload})
            task_list = await self._client.task_list(limit=10)
            self._store.dispatch({"kind": "rpc", "name": "task.list", "payload": task_list})
            self._store.dispatch(
                {
                    "kind": "ui",
                    "selected_task_id": task_id,
                    "active_screen": "task_detail",
                }
            )
            await self._load_task_related(task_id=task_id, run_id=run_id)
            self.switch_screen("task_detail")
            if self.screen.__class__.__name__ == "CreateTaskScreen":
                self.pop_screen()
            self._render_state()
            self._start_selected_task_stream(task_id=task_id, run_id=run_id)
        except ProtocolClientError as exc:
            if self.screen.__class__.__name__ == "CreateTaskScreen":
                self.screen.set_status(f"Create task failed: {exc}")  # type: ignore[attr-defined]

    async def _prime_config_snapshot(self) -> None:
        try:
            payload = await self._client.get_config()
            self._store.dispatch({"kind": "rpc", "name": "config.get", "payload": payload})
            self._ensure_config_selection()
        except ProtocolClientError:
            return

    async def _refresh_memory_inspection(
        self,
        *,
        task_id: str | None,
        run_id: str | None,
    ) -> None:
        context_key = f"{task_id}:{run_id}" if task_id and run_id else (task_id or "global")
        self._store.dispatch(
            {
                "kind": "ui",
                "memory_request_context_key": context_key,
                "memory_request_status": "loading",
                "memory_request_error": None,
            }
        )
        self._render_state()
        try:
            payload = await self._client.memory_inspect(task_id=task_id, run_id=run_id)
            payload = {
                **payload,
                "context": {
                    "task_id": task_id,
                    "run_id": run_id,
                },
            }
            self._store.dispatch({"kind": "rpc", "name": "memory.inspect", "payload": payload})
            self._ensure_memory_selection()
        except ProtocolClientError as exc:
            self._store.dispatch(
                {
                    "kind": "ui",
                    "memory_request_context_key": context_key,
                    "memory_request_status": "error",
                    "memory_request_error": str(exc),
                }
            )
        self._render_state()

    def _ensure_memory_selection(self) -> None:
        state = self._store.snapshot()
        groups = memory_scope_groups(state)
        selected_group = next(
            (group for group in groups if group.is_selected), groups[0] if groups else None
        )
        message: UiMessage = {"kind": "ui"}
        if selected_group is not None:
            message["selected_memory_group_id"] = selected_group.group_id
        detail = selected_memory_detail(state)
        if detail.status == "loaded":
            entries = memory_entry_items(self._store.snapshot())
            if entries:
                selected_entry = next((entry for entry in entries if entry.is_selected), entries[0])
                message["selected_memory_entry_id"] = selected_entry.memory_id
        self._store.dispatch(message)

    def _ensure_config_selection(self) -> None:
        sections = config_section_items(self._store.snapshot())
        if not sections:
            return
        selected = next((section for section in sections if section.is_selected), sections[0])
        self._store.dispatch({"kind": "ui", "selected_config_section_id": selected.section_id})

    def _ensure_diagnostic_selection(self) -> None:
        items = diagnostics_items(self._store.snapshot())
        if not items:
            return
        selected = next((item for item in items if item.is_selected), items[0])
        self._store.dispatch({"kind": "ui", "selected_diagnostic_id": selected.diagnostic_id})


def _default_workspace_root(config_snapshot: dict[str, Any]) -> str | None:
    cli = config_snapshot.get("cli")
    if not isinstance(cli, dict):
        return None
    workspace_root = cli.get("default_workspace_root")
    if not isinstance(workspace_root, str) or not workspace_root.strip():
        return None
    return workspace_root
