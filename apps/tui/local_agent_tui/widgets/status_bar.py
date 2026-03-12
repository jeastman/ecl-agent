from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import (
    approval_count,
    artifact_count,
    connection_label,
    diagnostics_count,
    runtime_health_label,
    status_bar_memory_status,
    status_bar_model_name,
    status_bar_sandbox_mode,
    task_count,
)
from ..theme.colors import ACCENT, DANGER, SUCCESS, TEXT_PRIMARY, WARNING

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class StatusBar(Static):  # type: ignore[misc]
    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        runtime_name = str(state.runtime_health.get("runtime_name", "runtime"))
        transport = str(state.runtime_health.get("transport", "unknown"))
        model_name = status_bar_model_name(state)
        sandbox_mode = status_bar_sandbox_mode(state)
        status_color = {
            "connected": SUCCESS,
            "connecting": WARNING,
            "error": DANGER,
        }.get(state.connection_status, TEXT_PRIMARY)
        memory_status = status_bar_memory_status(state)
        segments = [
            f"[bold {ACCENT}]LOCAL AGENT HARNESS[/]",
            f"Name: {runtime_name}",
            f"Runtime: [{status_color}]{connection_label(state)}[/]",
            f"Health: {runtime_health_label(state)}",
            f"Transport: {transport}",
            f"Model: {model_name}" if model_name else "",
            f"Sandbox: {sandbox_mode}" if sandbox_mode else "",
            f"Tasks: {task_count(state)}",
            f"Approvals: [{WARNING}]{approval_count(state)}[/]",
            f"Artifacts: [{ACCENT}]{artifact_count(state)}[/]",
            f"Diagnostics: [{DANGER}]{diagnostics_count(state)}[/]",
            f"Memory: {memory_status}",
            "G Palette",
            "N New Task",
        ]
        self.update(" | ".join(segment for segment in segments if segment))
