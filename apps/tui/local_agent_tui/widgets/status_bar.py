from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text

from ..renderables import badge, join, muted, text
from ..store.app_state import AppState
from ..store.selectors import (
    approval_count,
    artifact_count,
    diagnostics_count,
    screen_breadcrumb,
    status_bar_model_name,
    task_count,
)
from ..theme.colors import (
    ACCENT_PRIMARY,
    STATUS_DANGER,
    STATUS_RUNNING,
    STATUS_WARNING,
    TEXT_MUTED_DEEP,
    TEXT_SECONDARY,
)

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.widget import Widget as _Widget
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.widget import Widget as _Widget
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        _Widget = cast(Any, object)
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


def _render_identity_bar(state: AppState, clock_str: str) -> Text:
    """Render the top identity bar as Rich Text.

    Format: APP NAME  ● runtime-name  model-name  HH:MM:SS
    """
    result = Text()
    # App name
    result.append("LOCAL AGENT HARNESS", style=f"bold {ACCENT_PRIMARY}")
    result.append("  ")

    # Connection dot
    dot_color = {
        "connected": STATUS_RUNNING,
        "connecting": STATUS_WARNING,
        "error": STATUS_DANGER,
    }.get(state.connection_status, TEXT_MUTED_DEEP)
    dot = "●" if state.connection_status == "connected" else "○"
    result.append(dot, style=dot_color)
    result.append("  ")

    # Runtime name
    runtime_name = str(state.runtime_health.get("runtime_name", "runtime"))
    result.append(runtime_name, style=TEXT_SECONDARY)

    # Model name
    model_name = status_bar_model_name(state)
    if model_name:
        result.append("  ")
        result.append(model_name, style=TEXT_SECONDARY)

    # Clock
    if clock_str:
        result.append("  ")
        result.append(clock_str, style=TEXT_MUTED_DEEP)

    return result


def _render_context_bar(state: AppState) -> Text:
    """Render the context bar (breadcrumb + count badges) as Rich Text."""
    result = Text()

    # Breadcrumb (left side)
    result.append_text(screen_breadcrumb(state))

    # Count badges (pipe-separated, right side)
    t_count = task_count(state)
    a_count = approval_count(state)
    art_count = artifact_count(state)
    d_count = diagnostics_count(state)

    result.append("  │  ", style=TEXT_MUTED_DEEP)
    result.append(f"Tasks {t_count}", style=TEXT_SECONDARY)

    result.append("  │  ", style=TEXT_MUTED_DEEP)
    if a_count > 0:
        result.append(f"⚠ Approvals {a_count}", style=STATUS_WARNING)
    else:
        result.append(f"Approvals {a_count}", style=TEXT_SECONDARY)

    result.append("  │  ", style=TEXT_MUTED_DEEP)
    result.append(f"Artifacts {art_count}", style=TEXT_SECONDARY)

    result.append("  │  ", style=TEXT_MUTED_DEEP)
    if d_count > 0:
        result.append(f"Diagnostics {d_count}", style=STATUS_DANGER)
    else:
        result.append(f"Diagnostics {d_count}", style=TEXT_SECONDARY)

    return result


class StatusBar(_Widget):  # type: ignore[misc]
    """Two-row status bar: identity bar (top) + context bar (bottom).

    Extends Widget (not Static) because it composes child Static widgets.
    The identity bar shows app name, connection status, runtime/model name,
    and a clock updated every second via set_interval.
    The context bar shows a breadcrumb trail and count badges.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_state: AppState | None = None
        self._clock_str: str = ""

    def compose(self) -> ComposeResult:  # type: ignore[override]
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required") from _TEXTUAL_IMPORT_ERROR
        yield Static("", id="identity-bar")
        yield Static("", id="context-bar")

    def on_mount(self) -> None:  # pragma: no cover
        self.set_interval(1.0, self._tick_clock)

    def _tick_clock(self) -> None:  # pragma: no cover
        self._clock_str = datetime.now().strftime("%H:%M:%S")
        if self._last_state is not None:
            self._refresh_identity_bar(self._last_state)

    def _refresh_identity_bar(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            return
        self.query_one("#identity-bar", Static).update(
            _render_identity_bar(state, self._clock_str)
        )

    def update_from_state(self, state: AppState) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required") from _TEXTUAL_IMPORT_ERROR
        self._last_state = state
        self._refresh_identity_bar(state)
        self.query_one("#context-bar", Static).update(_render_context_bar(state))
