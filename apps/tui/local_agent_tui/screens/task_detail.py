from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.app_state import AppState
from ..store.selectors import footer_hints, selected_task_summary

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.screen import Screen
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container
        from textual.screen import Screen
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        Screen = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class TaskDetailScreen(Screen):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        yield Container(
            Static(id="task-detail-body"), Static(id="task-detail-footer"), id="task-detail-root"
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        summary = selected_task_summary(state)
        body = self.query_one("#task-detail-body", Static)
        body.border_title = "Task Detail"
        if summary is None:
            body.update("No task selected.")
        else:
            body.update(
                "\n".join(
                    [
                        f"{summary.task_id}  {summary.status.upper()}  {summary.run_id}",
                        f"Created: {summary.created_at}",
                        f"Updated: {summary.updated_at}",
                        "",
                        summary.objective,
                        "",
                        summary.latest_summary,
                    ]
                )
            )
        self.query_one("#task-detail-footer", Static).update("   ".join(footer_hints(state)))
