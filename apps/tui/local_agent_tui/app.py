from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from .protocol.event_stream import consume_task_stream
from .protocol.protocol_client import ProtocolClient, ProtocolClientError
from .screens.approvals import ApprovalsScreen
from .screens.dashboard import DashboardScreen
from .screens.task_detail import TaskDetailScreen
from .store.app_state import AppStateStore
from .store.selectors import (
    pending_approvals,
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
        Binding("tab", "focus_next_pane", "Next Pane", show=False, priority=True),
        Binding("shift+tab", "focus_prev_pane", "Prev Pane", show=False, priority=True),
        Binding("enter", "open_task", "Open Task", show=False, priority=True),
        Binding("a", "open_approvals", "Approvals", show=False, priority=True),
        Binding("r", "resume_task", "Resume", show=False, priority=True),
        Binding("o", "select_next_artifact", "Artifact", show=False, priority=True),
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
        self.install_screen(DashboardScreen(), name="dashboard")
        self.install_screen(TaskDetailScreen(), name="task_detail")
        self.install_screen(ApprovalsScreen(), name="approvals")

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
            self._render_state()
            return
        self.call_from_thread(self._render_state)

    def _render_state(self) -> None:
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
        self._store.dispatch({"kind": "ui", "active_screen": screen_name})
        self.switch_screen(screen_name)
        self._render_state()

    def action_move_up(self) -> None:
        self._move_focused_selection(-1)

    def action_move_down(self) -> None:
        self._move_focused_selection(1)

    def _move_focused_selection(self, delta: int) -> None:
        state = self._store.snapshot()
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
        current_index = panes.index(state.focused_pane) if state.focused_pane in panes else 0
        next_index = (current_index + delta) % len(panes)
        self._store.dispatch({"kind": "ui", "focused_pane": panes[next_index]})
        self._render_state()

    def action_open_task(self) -> None:
        state = self._store.snapshot()
        if state.active_screen == "approvals":
            self.action_open_selected_approval_task()
            return
        if state.active_screen == "dashboard" and state.focused_pane == "approvals":
            self._set_active_screen("approvals")
            return
        if state.selected_task_id is None:
            return
        self._set_active_screen("task_detail")

    def action_open_approvals(self) -> None:
        self._set_active_screen("approvals")

    def action_resume_task(self) -> None:
        state = self._store.snapshot()
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

    def action_select_next_artifact(self) -> None:
        state = self._store.snapshot()
        if state.active_screen != "task_detail":
            return
        artifacts = task_artifact_panel(state)
        if not artifacts:
            return
        current_index = next(
            (index for index, artifact in enumerate(artifacts) if artifact.is_selected),
            -1,
        )
        next_artifact = artifacts[(current_index + 1) % len(artifacts)]
        self._store.dispatch({"kind": "ui", "selected_artifact_id": next_artifact.artifact_id})
        self._render_state()

    def action_back_dashboard(self) -> None:
        self._set_active_screen("dashboard")

    async def action_quit(self) -> None:
        self.exit()

    def action_open_selected_approval_task(self) -> None:
        state = self._store.snapshot()
        approvals = pending_approvals(state)
        if not approvals:
            return
        selected = next(
            (
                approval
                for approval in approvals
                if approval.approval_id == state.selected_approval_id
            ),
            approvals[0],
        )
        self._store.dispatch(
            {
                "kind": "ui",
                "selected_task_id": selected.task_id,
                "focused_pane": "tasks",
            }
        )
        self._set_active_screen("task_detail")

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
