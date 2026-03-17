from __future__ import annotations

import unittest
from email.message import Message
from urllib.error import URLError

from services.web_service.local_agent_web_service import (
    DuckDuckGoSearchAdapter,
    SimpleMarkdownWebFetchAdapter,
    WebFetchError,
    WebSearchError,
)


class WebFetchAdapterTests(unittest.TestCase):
    def test_html_fetch_converts_to_markdown_and_tracks_redirect(self) -> None:
        captured_headers: dict[str, str] = {}
        adapter = SimpleMarkdownWebFetchAdapter(
            opener=_static_opener(
                body=(
                    "<html><head><title>Example</title></head>"
                    "<body><h1>Heading</h1><p>Hello <a href='https://example.com'>world</a>.</p></body></html>"
                ),
                content_type="text/html; charset=utf-8",
                final_url="https://example.com/final",
                status=200,
                captured_headers=captured_headers,
            )
        )

        document = adapter.fetch("https://example.com")

        self.assertEqual(document.final_url, "https://example.com/final")
        self.assertEqual(document.title, "Example")
        self.assertIn("# Example", document.markdown_content)
        self.assertIn("# Heading", document.markdown_content)
        self.assertIn("[Hello world](https://example.com)", document.markdown_content)
        self.assertEqual(captured_headers["Accept"], "text/markdown, text/html;q=0.9")

    def test_markdown_response_is_used_directly(self) -> None:
        adapter = SimpleMarkdownWebFetchAdapter(
            opener=_static_opener(
                body="# Direct Markdown\n\nAlready normalized.",
                content_type="text/markdown; charset=utf-8",
                final_url="https://example.com/markdown",
                status=200,
            )
        )

        document = adapter.fetch("https://example.com/markdown")

        self.assertEqual(document.content_type, "text/markdown")
        self.assertEqual(document.markdown_content, "# Direct Markdown\n\nAlready normalized.")

    def test_non_html_fetch_returns_controlled_error(self) -> None:
        adapter = SimpleMarkdownWebFetchAdapter(
            opener=_static_opener(
                body="plain text",
                content_type="text/plain; charset=utf-8",
                final_url="https://example.com/file.txt",
                status=200,
            )
        )

        with self.assertRaisesRegex(WebFetchError, "unsupported content type"):
            adapter.fetch("https://example.com/file.txt")

    def test_fetch_enforces_size_limit(self) -> None:
        adapter = SimpleMarkdownWebFetchAdapter(
            opener=_static_opener(
                body="<html><body><p>abcdef</p></body></html>",
                content_type="text/html; charset=utf-8",
                final_url="https://example.com/large",
                status=200,
            )
        )

        with self.assertRaisesRegex(WebFetchError, "size limit"):
            adapter.fetch("https://example.com/large", max_bytes=5)


class DuckDuckGoSearchAdapterTests(unittest.TestCase):
    def test_search_normalizes_results_and_enforces_limit(self) -> None:
        adapter = DuckDuckGoSearchAdapter(
            opener=_static_opener(
                body="""
                <html><body>
                  <a class="result__a" href="https://example.com/one">One result</a>
                  <a class="result__snippet">First snippet</a>
                  <a class="result__a" href="https://example.com/two">Two result</a>
                  <a class="result__snippet">Second snippet</a>
                </body></html>
                """,
                content_type="text/html; charset=utf-8",
                final_url="https://duckduckgo.com/html/?q=test",
                status=200,
            )
        )

        results = adapter.search("test query", limit=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "One result")
        self.assertEqual(results[0].snippet, "First snippet")
        self.assertEqual(results[0].rank, 1)

    def test_search_returns_empty_list_when_no_results_exist(self) -> None:
        adapter = DuckDuckGoSearchAdapter(
            opener=_static_opener(
                body="<html><body><p>No results</p></body></html>",
                content_type="text/html; charset=utf-8",
                final_url="https://duckduckgo.com/html/?q=none",
                status=200,
            )
        )

        self.assertEqual(adapter.search("no results"), [])

    def test_search_wraps_upstream_failures(self) -> None:
        def failing_opener(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise URLError("offline")

        adapter = DuckDuckGoSearchAdapter(opener=failing_opener)

        with self.assertRaisesRegex(WebSearchError, "offline"):
            adapter.search("agent")


class _StaticResponse:
    def __init__(self, *, body: str, content_type: str, final_url: str, status: int) -> None:
        self._payload = body.encode("utf-8")
        self._final_url = final_url
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def read(self, amount: int | None = None) -> bytes:
        if amount is None:
            return self._payload
        return self._payload[:amount]

    def geturl(self) -> str:
        return self._final_url

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> _StaticResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None


def _static_opener(
    *,
    body: str,
    content_type: str,
    final_url: str,
    status: int,
    captured_headers: dict[str, str] | None = None,
):
    def _open(*args, **kwargs):  # type: ignore[no-untyped-def]
        request = args[0]
        if captured_headers is not None:
            captured_headers["Accept"] = request.get_header("Accept") or ""
        return _StaticResponse(
            body=body,
            content_type=content_type,
            final_url=final_url,
            status=status,
        )

    return _open


if __name__ == "__main__":
    unittest.main()
