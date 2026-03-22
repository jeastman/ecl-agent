from __future__ import annotations

from datetime import datetime, timezone


def relative_time(iso_timestamp: str) -> str:
    """ISO 8601 -> human-readable relative ('2m ago', 'just now', 'Mar 15').

    Thresholds:
    - < 10s  -> "just now"
    - < 60s  -> "{n}s ago"
    - < 60m  -> "{n}m ago"
    - < 24h  -> "{n}h ago"
    - < 7d   -> "{n}d ago"
    - else   -> "Mar 15" (month abbreviation + day)

    Gracefully returns the raw value on parse error.
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        delta = now - dt
        seconds = delta.total_seconds()
        # Future timestamps (negative delta) fall through to "just now" — acceptable for display

        if seconds < 10:
            return "just now"
        if seconds < 60:
            return f"{int(seconds)}s ago"
        if seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        if seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        if seconds < 7 * 86400:
            return f"{int(seconds // 86400)}d ago"
        return f"{dt.strftime('%b')} {dt.day}"
    except (ValueError, TypeError, OverflowError):
        return iso_timestamp if isinstance(iso_timestamp, str) else ""


def compact_time(iso_timestamp: str) -> str:
    """ISO 8601 -> 'HH:MM:SS' in local timezone. Fallback: raw value."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone()
        return local_dt.strftime("%H:%M:%S")
    except (ValueError, TypeError, OverflowError):
        return iso_timestamp if isinstance(iso_timestamp, str) else ""


def compact_datetime(iso_timestamp: str) -> str:
    """ISO 8601 -> 'YYYY-MM-DD HH:MM' in local timezone. Fallback: raw value."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OverflowError):
        return iso_timestamp if isinstance(iso_timestamp, str) else ""


def elapsed_duration(iso_timestamp: str) -> str:
    """ISO 8601 -> compact elapsed duration like '14m 32s'."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        seconds = max(0, int((datetime.now(tz=timezone.utc) - dt).total_seconds()))
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours}h {minutes}m"
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"
    except (ValueError, TypeError, OverflowError):
        return iso_timestamp if isinstance(iso_timestamp, str) else ""
