from __future__ import annotations


def truncate(text: str, width: int, *, suffix: str = "\u2026") -> str:
    """Truncate to width, appending suffix if truncated. Width includes suffix.

    - If len(text) <= width, return as-is.
    - Otherwise return text[:width - len(suffix)] + suffix.
    - Edge case: if width <= 0, return "" safely.
    """
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    cut = width - len(suffix)
    if cut <= 0:
        return suffix[:width]
    return text[:cut] + suffix


def truncate_id(value: str, width: int = 16) -> str:
    """Smart ID truncation: preserves prefix_XXXXXXXX format.

    Examples:
        "tsk_abc123def456" -> "tsk_abc1...f456" at width=16.

    Falls back to truncate() for IDs without underscore separators.

    Algorithm:
    - If len(value) <= width, return as-is.
    - Split on first underscore: prefix + "_" + rest.
    - If no underscore, use truncate(value, width).
    - If has underscore: keep prefix+"_" + first chars of rest + "..." + last 4
      chars of rest such that total length == width.
    """
    if len(value) <= width:
        return value

    sep = value.find("_")
    if sep == -1:
        return truncate(value, width)

    prefix = value[: sep + 1]  # includes the underscore
    rest = value[sep + 1 :]
    tail_len = 4
    ellipsis = "\u2026"
    # total = len(prefix) + middle_chars + 1 (ellipsis) + tail_len
    middle_len = width - len(prefix) - len(ellipsis) - tail_len
    if middle_len <= 0:
        # Not enough room for the smart format; fall back to plain truncate
        return truncate(value, width)
    return prefix + rest[:middle_len] + ellipsis + rest[-tail_len:]
