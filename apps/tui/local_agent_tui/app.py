from __future__ import annotations

from dataclasses import dataclass

from .protocol.event_stream import consume_task_stream
from .protocol.protocol_client import ProtocolClient, ProtocolClientError
from .store.app_state import AppStateStore
from .widgets.status_bar import StatusBar

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container
    from textual.widgets import Static
except ModuleNotFoundError as exc:  # pragma: no cover
    App = object  # type: ignore[assignment]
    ComposeResult = object  # type: ignore[assignment]
    Container = object  # type: ignore[assignment]
    Static = object  # type: ignore[assignment]
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

    def __init__(self, *, config_path: str, task_id: str | None, run_id: str | None) -> None:
        ensure_textual_available()
        super().__init__()
        self._bootstrap = BootstrapConfig(config_path=config_path, task_id=task_id, run_id=run_id)
        self._client = ProtocolClient(config_path)
        self._store = AppStateStore()
        self._status_bar = StatusBar(id="status-bar")
        self._shell = Static("Connecting to runtime...", id="shell-body")

    def compose(self) -> ComposeResult:
        yield self._status_bar
        yield Container(self._shell, id="shell")

    async def on_mount(self) -> None:
        self._store.dispatch({"kind": "connection", "status": "connecting"})
        self._render_state()
        self.run_worker(self._connect_and_refresh())
        if self._bootstrap.task_id is not None:
            self.run_worker(
                self._attach_task(
                    task_id=self._bootstrap.task_id,
                    run_id=self._bootstrap.run_id,
                )
            )

    async def on_unmount(self) -> None:
        await self._client.close()

    async def _connect_and_refresh(self) -> None:
        try:
            await self._client.connect()
            self._store.dispatch({"kind": "connection", "status": "connected"})
            health = await self._client.runtime_health()
            self._store.dispatch({"kind": "rpc", "name": "runtime.health", "payload": health})
            self._render_state()
        except ProtocolClientError as exc:
            self._store.dispatch({"kind": "connection", "status": "error", "error": str(exc)})
            self._render_state()

    async def _attach_task(self, *, task_id: str, run_id: str | None) -> None:
        try:
            task = await self._client.task_get(task_id, run_id)
            self._store.dispatch({"kind": "rpc", "name": "task.get", "payload": task})
            approvals = await self._client.task_approvals_list(task_id, run_id)
            self._store.dispatch({"kind": "rpc", "name": "task.approvals.list", "payload": approvals})
            artifacts = await self._client.task_artifacts_list(task_id, run_id)
            self._store.dispatch({"kind": "rpc", "name": "task.artifacts.list", "payload": artifacts})
            self._render_state()
            await consume_task_stream(
                self._client,
                task_id=task_id,
                run_id=run_id,
                dispatch=self._dispatch_and_render,
            )
        except ProtocolClientError as exc:
            self._store.dispatch({"kind": "connection", "status": "error", "error": str(exc)})
            self._render_state()

    def _dispatch_and_render(self, message: dict[str, object]) -> None:
        self._store.dispatch(message)  # type: ignore[arg-type]
        self.call_from_thread(self._render_state)

    def _render_state(self) -> None:
        state = self._store.snapshot()
        self._status_bar.update_from_state(state)
        if state.selected_task_id is None:
            self._shell.update("Runtime connected. Attach with --task-id to tail a task stream.")
            return
        snapshot = state.task_snapshots.get(state.selected_task_id, {})
        status = snapshot.get("status", "unknown")
        summary = snapshot.get("latest_summary", "Waiting for runtime events.")
        self._shell.update(
            "\n".join(
                [
                    f"Selected task: {state.selected_task_id}",
                    f"Status: {status}",
                    f"Summary: {summary}",
                ]
            )
        )
