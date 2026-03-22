from __future__ import annotations

from rich.text import Text

EMPTY_STATES: dict[str, tuple[str, str, str]] = {
    "tasks":         ("◇", "No tasks yet",           "Press n to create your first task"),
    "events":        ("◇", "No events yet",           "Events will appear as the task executes"),
    "approvals":     ("✓", "No pending approvals.",   "All requests have been resolved"),
    "artifacts":     ("◇", "No artifacts",            "Artifacts will appear as the agent produces output"),
    "subagents":     ("◇", "No subagent activity",    "Subagents will appear when the task delegates work"),
    "plan":          ("◇", "No plan yet",             "A plan will appear when the agent begins strategizing"),
    "todos":         ("◇", "No todo list yet",        "The agent will populate tasks as it plans and executes"),
    "notifications": ("✓", "No urgent updates",       "You're all caught up"),
    "memory":        ("◇", "No memory entries",       "The agent hasn't stored any memories yet"),
    "diagnostics":   ("✓", "No diagnostics",          "No issues detected"),
    "config":        ("◇", "No config loaded",        "Config will load when the runtime connects"),
}


def render_empty_state(key: str) -> Text:
    """Return a centered 3-line Rich Text for a named empty state.
    Falls back gracefully for unknown keys."""
    if key not in EMPTY_STATES:
        result = Text(justify="center")
        result.no_wrap = True
        result.append("◇\n", style="dim")
        result.append("Nothing here\n", style="dim bold")
        return result

    icon, heading, hint = EMPTY_STATES[key]
    result = Text(justify="center")
    result.no_wrap = True
    result.append(f"{icon}\n", style="dim")
    result.append(f"{heading}\n", style="dim bold")
    result.append(hint, style="dim")
    return result
