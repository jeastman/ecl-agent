from __future__ import annotations

from typing import Any

from rich.markup import escape

from ..compat import Binding, ComposeResult, Container, Input, ModalScreen, Static


class TaskTimelinePromptScreen(ModalScreen[None]):  # type: ignore[misc]
    BINDINGS = [Binding("enter", "submit_prompt", "Submit", show=False, priority=True)]

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

    def action_submit_prompt(self) -> None:
        value = self.query_one(Input).value
        if self._mode == "search":
            self.app.submit_task_timeline_search(value)  # type: ignore[attr-defined]
        else:
            self.app.submit_task_timeline_filter(value)  # type: ignore[attr-defined]

    def set_status(self, message: str) -> None:
        self.query_one("#task-timeline-prompt-status", Static).update(escape(message))

    def on_key(self, event: Any) -> None:
        key = getattr(event, "key", "")
        if key == "escape":
            self.app.close_task_timeline_prompt()  # type: ignore[attr-defined]
            event.stop()
        elif key == "enter":
            self.action_submit_prompt()
            event.stop()
