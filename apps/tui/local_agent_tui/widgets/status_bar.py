from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.text import Text

from ..renderables import badge, join, muted, text
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
        segments: list[Text] = [
            text("LOCAL AGENT HARNESS", style=f"bold {ACCENT}"),
            join([muted("Name"), text(runtime_name)], separator=": "),
            join([muted("Runtime"), badge(connection_label(state), style=status_color)], separator=": "),
            join([muted("Health"), text(runtime_health_label(state))], separator=": "),
            join([muted("Transport"), text(transport)], separator=": "),
        ]
        if model_name:
            segments.append(join([muted("Model"), text(model_name)], separator=": "))
        if sandbox_mode:
            segments.append(join([muted("Sandbox"), text(sandbox_mode)], separator=": "))
        segments.extend(
            [
                join([muted("Tasks"), text(str(task_count(state)))], separator=": "),
                join([muted("Approvals"), badge(str(approval_count(state)), style=WARNING)], separator=": "),
                join([muted("Artifacts"), badge(str(artifact_count(state)), style=ACCENT)], separator=": "),
                join([muted("Diagnostics"), badge(str(diagnostics_count(state)), style=DANGER)], separator=": "),
                join([muted("Memory"), text(memory_status)], separator=": "),
            ]
        )
        self.update(_fit_status_bar(segments, self.size.width or 120))


def _fit_status_bar(segments: list[Text], width: int) -> Text:
    visible_segments = [segment for segment in segments if segment.plain]
    if width <= 0:
        return join(visible_segments, separator=" | ")
    joined = Text()
    used_width = 0
    visible_count = 0
    for segment in visible_segments:
        segment_width = segment.cell_len
        separator_width = 3 if visible_count else 0
        if visible_count and used_width + separator_width + segment_width > width:
            break
        if not visible_count and segment_width > width:
            clipped = segment.copy()
            clipped.truncate(width, overflow="ellipsis")
            return clipped
        if visible_count:
            joined.append(" | ")
        joined.append_text(segment.copy())
        used_width += separator_width + segment_width
        visible_count += 1
        if visible_count < len(visible_segments) and used_width + 5 > width:
            break
    omitted = len(visible_segments) - visible_count
    if omitted > 0:
        ellipsis = badge("...", style=WARNING)
        if joined and used_width + 3 + ellipsis.cell_len <= width:
            joined.append(" | ")
            joined.append_text(ellipsis)
        elif not joined:
            return ellipsis
    return joined
