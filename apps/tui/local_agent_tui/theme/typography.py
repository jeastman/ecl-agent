from __future__ import annotations

from rich.text import Text
from .colors import (TEXT_TITLE, TEXT_SECONDARY, TEXT_MUTED_DEEP,
                     STATUS_RUNNING, STATUS_SUCCESS, STATUS_WARNING,
                     STATUS_DANGER, STATUS_INFO)

TEXT_PRIMARY = "#e8edf2"  # local constant for value() function

STATUS_COLORS: dict[str, str] = {
    "executing": STATUS_RUNNING,
    "planning": STATUS_RUNNING,
    "running": STATUS_RUNNING,
    "completed": STATUS_SUCCESS,
    "failed": STATUS_DANGER,
    "paused": STATUS_WARNING,
    "awaiting_approval": STATUS_WARNING,
    "accepted": STATUS_RUNNING,
}


def title(text: str) -> Text:
    """Bold TEXT_TITLE colored text."""
    return Text(text, style=f"bold {TEXT_TITLE}")


def label(text: str) -> Text:
    """TEXT_SECONDARY colored text."""
    return Text(text, style=TEXT_SECONDARY)


def value(text: str) -> Text:
    """TEXT_PRIMARY (#e8edf2) colored text."""
    return Text(text, style=TEXT_PRIMARY)


def muted(text: str) -> Text:
    """TEXT_MUTED_DEEP colored text."""
    return Text(text, style=TEXT_MUTED_DEEP)


def status_badge(status: str) -> Text:
    """Bold colored ' STATUS ' badge.

    Uses STATUS_COLORS dict; falls back to STATUS_INFO for unknown statuses.
    Format: ' {STATUS.UPPER()} ' with padding spaces.
    """
    color = STATUS_COLORS.get(status.lower(), STATUS_INFO)
    return Text(f" {status.upper()} ", style=f"bold black on {color}")


def key_hint(key: str, action: str) -> Text:
    """' KEY ' in bold reverse style + ' action' in TEXT_SECONDARY."""
    result = Text()
    result.append(f" {key} ", style="bold reverse")
    result.append(f" {action}", style=TEXT_SECONDARY)
    return result
