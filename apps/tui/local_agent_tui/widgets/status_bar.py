from __future__ import annotations

from ..store.app_state import AppState
from ..store.selectors import approval_count, artifact_count, connection_label, runtime_health_label, task_count

try:
    from textual.widgets import Static
except ModuleNotFoundError as exc:  # pragma: no cover
    Static = object  # type: ignore[assignment]
    _TEXTUAL_IMPORT_ERROR = exc
else:
    _TEXTUAL_IMPORT_ERROR = None


class StatusBar(Static):  # type: ignore[misc]
    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.update(
            " | ".join(
                [
                    "LOCAL AGENT HARNESS",
                    f"Runtime: {connection_label(state)}",
                    f"Health: {runtime_health_label(state)}",
                    f"Tasks: {task_count(state)}",
                    f"Approvals: {approval_count(state)}",
                    f"Artifacts: {artifact_count(state)}",
                ]
            )
        )
