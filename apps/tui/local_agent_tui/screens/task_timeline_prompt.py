from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.screen import ModalScreen
    from textual.widgets import Input, Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import Container
        from textual.screen import ModalScreen
        from textual.widgets import Input, Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        Container = cast(Any, object)
        ModalScreen = cast(Any, object)
        Input = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class TaskTimelinePromptScreen(ModalScreen[None]):  # type: ignore[misc]
    def __init__(self, *, mode: str) -> None:
        super().__init__()
        self._mode = mode

    def compose(self) -> ComposeResult:
        title = "Search timeline" if self._mode == "search" else "Filter timeline"
        placeholder = (
            "Blank clears search"
            if self._mode == "search"
            else "all, important, tools, plans, approvals, artifacts, subagents, errors"
        )
        help_text = (
            "Search summaries, event types, source names, and payload text. Enter submits."
            if self._mode == "search"
            else "Enter submits. Blank resets to all."
        )
        yield Container(
            Static(title, id="task-timeline-prompt-title"),
            Input(placeholder=placeholder, id="task-timeline-prompt-input"),
            Static(help_text, id="task-timeline-prompt-status"),
            id="task-timeline-prompt-panel",
        )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._mode == "search":
            self.app.submit_task_timeline_search(event.value)  # type: ignore[attr-defined]
        else:
            self.app.submit_task_timeline_filter(event.value)  # type: ignore[attr-defined]

    def set_status(self, message: str) -> None:
        self.query_one("#task-timeline-prompt-status", Static).update(message)

    def on_key(self, event: Any) -> None:
        if getattr(event, "key", "") == "escape":
            self.app.close_task_timeline_prompt()  # type: ignore[attr-defined]
            event.stop()
