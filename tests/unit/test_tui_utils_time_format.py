from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from apps.tui.local_agent_tui.utils.time_format import (
    compact_datetime,
    compact_time,
    relative_time,
)


def _ts(delta_seconds: float) -> str:
    """Return an ISO 8601 UTC timestamp that is delta_seconds in the past."""
    dt = datetime.now(tz=timezone.utc) - timedelta(seconds=delta_seconds)
    return dt.isoformat()


class TestRelativeTime(unittest.TestCase):
    def test_just_now_less_than_10s(self) -> None:
        self.assertEqual(relative_time(_ts(5)), "just now")

    def test_just_now_boundary_exactly_0s(self) -> None:
        self.assertEqual(relative_time(_ts(0)), "just now")

    def test_seconds_ago(self) -> None:
        result = relative_time(_ts(30))
        self.assertRegex(result, r"^\d+s ago$")
        self.assertEqual(result, "30s ago")

    def test_seconds_boundary_59s(self) -> None:
        result = relative_time(_ts(59))
        self.assertRegex(result, r"^\d+s ago$")

    def test_minutes_ago(self) -> None:
        result = relative_time(_ts(120))
        self.assertEqual(result, "2m ago")

    def test_minutes_ago_boundary_59m(self) -> None:
        result = relative_time(_ts(59 * 60))
        self.assertRegex(result, r"^\d+m ago$")

    def test_hours_ago(self) -> None:
        result = relative_time(_ts(7200))
        self.assertEqual(result, "2h ago")

    def test_hours_ago_boundary_23h(self) -> None:
        result = relative_time(_ts(23 * 3600))
        self.assertRegex(result, r"^\d+h ago$")

    def test_days_ago(self) -> None:
        result = relative_time(_ts(2 * 86400))
        self.assertEqual(result, "2d ago")

    def test_days_ago_boundary_6d(self) -> None:
        result = relative_time(_ts(6 * 86400))
        self.assertRegex(result, r"^\d+d ago$")

    def test_short_date_older_than_7d(self) -> None:
        # Use a fixed timestamp well in the past so the result is deterministic.
        result = relative_time("2024-01-15T12:00:00+00:00")
        self.assertRegex(result, r"^[A-Z][a-z]{2} \d+$")
        self.assertEqual(result, "Jan 15")

    def test_short_date_month_abbreviation(self) -> None:
        result = relative_time("2023-03-07T00:00:00+00:00")
        self.assertEqual(result, "Mar 7")

    def test_future_timestamp_returns_just_now(self) -> None:
        # A timestamp 60 seconds in the future has a negative delta; falls through to "just now".
        future_ts = (datetime.now(tz=timezone.utc) + timedelta(seconds=60)).isoformat()
        self.assertEqual(relative_time(future_ts), "just now")

    def test_malformed_input_returns_raw(self) -> None:
        self.assertEqual(relative_time("not-a-date"), "not-a-date")

    def test_empty_string_returns_raw(self) -> None:
        self.assertEqual(relative_time(""), "")


class TestCompactTime(unittest.TestCase):
    def test_utc_timestamp_produces_hhmmss(self) -> None:
        # Use a fixed UTC timestamp; convert to local for comparison.
        ts = "2024-06-15T14:30:45+00:00"
        dt = datetime.fromisoformat(ts).astimezone()
        expected = dt.strftime("%H:%M:%S")
        self.assertEqual(compact_time(ts), expected)

    def test_format_is_hhmmss(self) -> None:
        result = compact_time("2024-01-01T00:00:00+00:00")
        self.assertRegex(result, r"^\d{2}:\d{2}:\d{2}$")

    def test_malformed_input_returns_raw(self) -> None:
        self.assertEqual(compact_time("bad"), "bad")

    def test_empty_string_returns_raw(self) -> None:
        self.assertEqual(compact_time(""), "")


class TestCompactDatetime(unittest.TestCase):
    def test_utc_timestamp_produces_datetime(self) -> None:
        ts = "2024-06-15T14:30:00+00:00"
        dt = datetime.fromisoformat(ts).astimezone()
        expected = dt.strftime("%Y-%m-%d %H:%M")
        self.assertEqual(compact_datetime(ts), expected)

    def test_format_is_yyyy_mm_dd_hh_mm(self) -> None:
        result = compact_datetime("2024-01-01T00:00:00+00:00")
        self.assertRegex(result, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_malformed_input_returns_raw(self) -> None:
        self.assertEqual(compact_datetime("bad"), "bad")

    def test_empty_string_returns_raw(self) -> None:
        self.assertEqual(compact_datetime(""), "")


if __name__ == "__main__":
    unittest.main()
