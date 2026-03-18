from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from rich.markup import escape

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
            f"Name: {escape(runtime_name)}",
            f"Runtime: [{status_color}]{escape(connection_label(state))}[/]",
            f"Health: {escape(runtime_health_label(state))}",
            f"Transport: {escape(transport)}",
            f"Model: {escape(model_name)}" if model_name else "",
            f"Sandbox: {escape(sandbox_mode)}" if sandbox_mode else "",
            f"Tasks: {task_count(state)}",
            f"Approvals: [{WARNING}]{approval_count(state)}[/]",
            f"Artifacts: [{ACCENT}]{artifact_count(state)}[/]",
            f"Diagnostics: [{DANGER}]{diagnostics_count(state)}[/]",
            f"Memory: {escape(memory_status)}",
        ]
        self.update(_fit_status_bar(segments, self.size.width or 120))


def _fit_status_bar(segments: list[str], width: int) -> str:
    visible_segments = [segment for segment in segments if segment]
    if width <= 0:
        return " | ".join(visible_segments)
    joined_segments: list[str] = []
    used_width = 0
    for index, segment in enumerate(visible_segments):
        separator_width = 3 if joined_segments else 0
        segment_width = _display_width(segment)
        if joined_segments and used_width + separator_width + segment_width > width:
            break
        if not joined_segments and segment_width > width:
            return _truncate_markup(segment, width)
        joined_segments.append(segment)
        used_width += separator_width + segment_width
        remaining = len(visible_segments) - index - 1
        if remaining > 0 and used_width + 5 > width:
            break
    omitted = len(visible_segments) - len(joined_segments)
    if omitted > 0:
        ellipsis = f"[{WARNING}]...[/]"
        if joined_segments and used_width + 3 + _display_width(ellipsis) <= width:
            joined_segments.append(ellipsis)
        elif not joined_segments:
            return _truncate_markup(ellipsis, width)
    return " | ".join(joined_segments)


def _display_width(value: str) -> int:
    plain = re.sub(r"\[[^\]]*\]", "", value)
    return len(plain)


def _truncate_markup(value: str, width: int) -> str:
    plain = re.sub(r"\[[^\]]*\]", "", value)
    if len(plain) <= width:
        return value
    if width <= 3:
        return "." * max(width, 0)
    return plain[: width - 3].rstrip() + "..."
