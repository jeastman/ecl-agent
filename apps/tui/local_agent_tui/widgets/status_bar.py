from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import (
    approval_count,
    artifact_count,
    connection_label,
    runtime_health_label,
    task_count,
)

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
        self.update(
            " | ".join(
                [
                    "LOCAL AGENT HARNESS",
                    f"Name: {runtime_name}",
                    f"Runtime: {connection_label(state)}",
                    f"Health: {runtime_health_label(state)}",
                    f"Transport: {transport}",
                    f"Tasks: {task_count(state)}",
                    f"Approvals: {approval_count(state)}",
                    f"Artifacts: {artifact_count(state)}",
                ]
            )
        )
