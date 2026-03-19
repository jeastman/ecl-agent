from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.utils.text import truncate, truncate_id


class TestTruncate(unittest.TestCase):
    def test_no_op_when_fits_exactly(self) -> None:
        self.assertEqual(truncate("hello", 5), "hello")

    def test_no_op_when_shorter_than_width(self) -> None:
        self.assertEqual(truncate("hi", 10), "hi")

    def test_truncates_and_appends_default_ellipsis(self) -> None:
        # "hello world" (11) truncated to width=8 => "hello w" + "…" = 8 chars
        result = truncate("hello world", 8)
        self.assertEqual(len(result), 8)
        self.assertTrue(result.endswith("\u2026"))
        self.assertEqual(result, "hello w\u2026")

    def test_truncates_with_custom_suffix(self) -> None:
        result = truncate("hello world", 8, suffix="...")
        self.assertEqual(len(result), 8)
        self.assertTrue(result.endswith("..."))
        self.assertEqual(result, "hello...")

    def test_width_zero_returns_empty(self) -> None:
        self.assertEqual(truncate("anything", 0), "")

    def test_width_negative_returns_empty(self) -> None:
        self.assertEqual(truncate("anything", -5), "")

    def test_width_one_returns_suffix_truncated(self) -> None:
        # suffix "…" is 1 char, cut = 1 - 1 = 0 -> suffix[:1] = "…"
        result = truncate("hello", 1)
        self.assertEqual(result, "\u2026")

    def test_empty_string_no_op(self) -> None:
        self.assertEqual(truncate("", 5), "")

    def test_suffix_longer_than_width_still_safe(self) -> None:
        # suffix="..." (3), width=2 => cut = 2-3 = -1 <= 0 => suffix[:2] = ".."
        result = truncate("hello", 2, suffix="...")
        self.assertEqual(result, "..")


class TestTruncateId(unittest.TestCase):
    def test_short_id_no_truncation(self) -> None:
        self.assertEqual(truncate_id("tsk_abc", 16), "tsk_abc")

    def test_exact_length_no_truncation(self) -> None:
        value = "tsk_abc123def456"  # 16 chars
        self.assertEqual(truncate_id(value, 16), value)

    def test_smart_truncation_with_underscore(self) -> None:
        # "tsk_abc123def456xyz" -> width=16
        # prefix = "tsk_" (4), suffix tail = last 4 chars of rest
        # rest = "abc123def456xyz" (15 chars)
        # middle_len = 16 - 4 - 1 - 4 = 7
        # result = "tsk_" + "abc123d" + "…" + "456xyz"[-4:] = "tsk_abc123d…xyz"
        # rest = "abc123def456xyz"
        # middle_len = 16 - 4 - 1 - 4 = 7
        # result = "tsk_" + rest[:7] + "…" + rest[-4:]
        #        = "tsk_" + "abc123d" + "…" + "6xyz"
        #        = "tsk_abc123d…6xyz" (16 chars)
        value = "tsk_abc123def456xyz"
        result = truncate_id(value, 16)
        self.assertEqual(len(result), 16)
        self.assertTrue(result.startswith("tsk_"))
        self.assertIn("\u2026", result)
        self.assertEqual(result, "tsk_abc123d\u20266xyz")

    def test_smart_truncation_example_from_spec(self) -> None:
        # Spec: "tsk_abc123def456" -> "tsk_abc1…f456" at width=16
        # But "tsk_abc123def456" is exactly 16 chars, so no truncation needed.
        # Use a longer value to hit the truncation path:
        # "tsk_abc123def456extra" (21 chars) at width=16
        # prefix = "tsk_" (4), rest = "abc123def456extra" (17 chars)
        # middle_len = 16 - 4 - 1 - 4 = 7
        # result = "tsk_" + "abc123d" + "…" + "xtra"[-4:] -- rest[-4:] = "xtra"
        value = "tsk_abc123def456extra"
        result = truncate_id(value, 16)
        self.assertEqual(len(result), 16)
        self.assertTrue(result.startswith("tsk_"))
        self.assertIn("\u2026", result)

    def test_no_underscore_falls_back_to_truncate(self) -> None:
        value = "abcdefghijklmnopqrst"  # 20 chars, no underscore
        result = truncate_id(value, 16)
        self.assertEqual(len(result), 16)
        self.assertTrue(result.endswith("\u2026"))

    def test_no_underscore_short_falls_back_to_truncate_no_op(self) -> None:
        value = "abcdef"
        self.assertEqual(truncate_id(value, 16), "abcdef")

    def test_result_length_equals_width(self) -> None:
        # Any ID longer than width should produce exactly width chars
        value = "prefix_" + "x" * 30
        result = truncate_id(value, 20)
        self.assertEqual(len(result), 20)


if __name__ == "__main__":
    unittest.main()
