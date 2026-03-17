from __future__ import annotations

from dataclasses import replace
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

from packages.protocol.local_agent_protocol.models import utc_now_timestamp
from services.web_service.local_agent_web_service.models import (
    WebDocument,
    WebFetchError,
    WebSearchError,
    WebSearchResult,
)

_DEFAULT_USER_AGENT = "local-agent-harness/0.1"
_MARKDOWN_ACCEPT_HEADER = "text/markdown, text/html;q=0.9"


class SimpleMarkdownWebFetchAdapter:
    def __init__(
        self,
        *,
        opener: Callable[..., Any] | None = None,
        default_timeout: float = 10.0,
        default_max_bytes: int = 1_000_000,
        default_user_agent: str = _DEFAULT_USER_AGENT,
    ) -> None:
        self._opener = opener or urlopen
        self._default_timeout = default_timeout
        self._default_max_bytes = default_max_bytes
        self._default_user_agent = default_user_agent

    def fetch(
        self,
        url: str,
        *,
        max_bytes: int | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
    ) -> WebDocument:
        normalized_url = _normalize_http_url(url)
        request = Request(
            normalized_url,
            headers={
                "User-Agent": user_agent or self._default_user_agent,
                "Accept": _MARKDOWN_ACCEPT_HEADER,
            },
        )
        resolved_timeout = timeout or self._default_timeout
        resolved_max_bytes = max_bytes or self._default_max_bytes
        try:
            with self._opener(request, timeout=resolved_timeout) as response:
                content_type = _normalized_content_type(response.headers.get("Content-Type"))
                if content_type not in {"text/html", "text/markdown"}:
                    raise WebFetchError(f"unsupported content type: {content_type}")
                payload = response.read(resolved_max_bytes + 1)
                if len(payload) > resolved_max_bytes:
                    raise WebFetchError("response exceeded configured size limit")
                charset = response.headers.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
                rendered = (
                    _RenderedMarkdown(title=None, markdown_content=decoded)
                    if content_type == "text/markdown"
                    else _HTMLToMarkdownRenderer().render(decoded)
                )
                markdown = rendered.markdown_content.strip()
                if not markdown:
                    raise WebFetchError("fetched page did not contain readable text content")
                return WebDocument(
                    url=normalized_url,
                    final_url=response.geturl(),
                    title=rendered.title,
                    markdown_content=markdown,
                    fetched_at=utc_now_timestamp(),
                    content_type=content_type,
                    status_code=_response_status(response),
                )
        except HTTPError as exc:
            raise WebFetchError(f"web fetch failed with status {exc.code}") from exc
        except URLError as exc:
            raise WebFetchError(f"web fetch failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise WebFetchError("web fetch timed out") from exc


class DuckDuckGoSearchAdapter:
    def __init__(
        self,
        *,
        opener: Callable[..., Any] | None = None,
        default_timeout: float = 10.0,
        default_user_agent: str = _DEFAULT_USER_AGENT,
        max_results: int = 10,
    ) -> None:
        self._opener = opener or urlopen
        self._default_timeout = default_timeout
        self._default_user_agent = default_user_agent
        self._max_results = max_results

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        locale: str | None = None,
    ) -> list[WebSearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise WebSearchError("search query must not be empty")
        resolved_limit = max(1, min(limit, self._max_results))
        url = f"https://duckduckgo.com/html/?q={quote_plus(normalized_query)}"
        if locale:
            url += f"&kl={quote_plus(locale.strip())}"
        request = Request(url, headers={"User-Agent": self._default_user_agent})
        try:
            with self._opener(request, timeout=self._default_timeout) as response:
                payload = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                html = payload.decode(charset, errors="replace")
        except HTTPError as exc:
            raise WebSearchError(f"web search failed with status {exc.code}") from exc
        except URLError as exc:
            raise WebSearchError(f"web search failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise WebSearchError("web search timed out") from exc

        parser = _DuckDuckGoHTMLParser()
        parser.feed(html)
        return [
            replace(result, rank=index)
            for index, result in enumerate(parser.results[:resolved_limit], start=1)
        ]


class _RenderedMarkdown:
    def __init__(self, *, title: str | None, markdown_content: str) -> None:
        self.title = title
        self.markdown_content = markdown_content


class _HTMLToMarkdownRenderer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._title_parts: list[str] = []
        self._blocks: list[str] = []
        self._text_parts: list[str] = []
        self._current_href: str | None = None
        self._list_depth = 0
        self._heading_level: int | None = None
        self._ignore_depth = 0
        self._in_title = False

    def render(self, html: str) -> _RenderedMarkdown:
        self.feed(html)
        self.close()
        self._flush_block()
        title = _normalize_space("".join(self._title_parts)) or None
        body = "\n\n".join(block for block in self._blocks if block.strip())
        if title and not body.startswith(f"# {title}"):
            body = f"# {title}\n\n{body}".strip()
        return _RenderedMarkdown(title=title, markdown_content=body.strip())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignore_depth += 1
            return
        if self._ignore_depth:
            return
        if tag == "title":
            self._in_title = True
            return
        if tag in {"p", "div", "section", "article", "main", "header", "footer"}:
            self._flush_block()
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush_block()
            self._heading_level = int(tag[1])
            return
        if tag == "br":
            self._flush_inline()
            return
        if tag in {"ul", "ol"}:
            self._flush_block()
            self._list_depth += 1
            return
        if tag == "li":
            self._flush_block()
            self._text_parts.append(f"{'  ' * max(self._list_depth - 1, 0)}- ")
            return
        if tag == "a":
            attributes = dict(attrs)
            self._current_href = attributes.get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            if self._ignore_depth:
                self._ignore_depth -= 1
            return
        if self._ignore_depth:
            return
        if tag == "title":
            self._in_title = False
            return
        if tag in {"p", "div", "section", "article", "main", "header", "footer", "li"}:
            self._flush_block()
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush_block(prefix="#" * (self._heading_level or 1) + " ")
            self._heading_level = None
            return
        if tag in {"ul", "ol"}:
            self._flush_block()
            self._list_depth = max(0, self._list_depth - 1)
            return
        if tag == "a":
            self._finalize_link()

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        if self._in_title:
            self._title_parts.append(data)
            return
        if data.strip():
            self._text_parts.append(data)

    def _finalize_link(self) -> None:
        href = self._current_href
        self._current_href = None
        if href is None:
            return
        text = _normalize_space("".join(self._text_parts))
        if not text:
            return
        self._text_parts = [f"[{text}]({href})"]

    def _flush_inline(self) -> None:
        normalized = _normalize_space("".join(self._text_parts))
        if normalized:
            self._blocks.append(normalized)
        self._text_parts = []

    def _flush_block(self, prefix: str = "") -> None:
        normalized = _normalize_space("".join(self._text_parts))
        if normalized:
            self._blocks.append(f"{prefix}{normalized}".strip())
        self._text_parts = []


class _DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[WebSearchResult] = []
        self._capture_title = False
        self._capture_snippet = False
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []
        self._current_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        class_name = attributes.get("class") or ""
        if tag == "a" and "result__a" in class_name:
            self._capture_title = True
            self._current_title = []
            self._current_url = attributes.get("href")
            return
        if tag in {"a", "div", "span"} and "result__snippet" in class_name:
            self._capture_snippet = True
            self._current_snippet = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_title:
            self._capture_title = False
            title = _normalize_space("".join(self._current_title))
            if title and self._current_url:
                self.results.append(
                    WebSearchResult(
                        title=title,
                        url=self._current_url,
                        snippet="",
                        rank=0,
                        source="duckduckgo",
                    )
                )
            self._current_title = []
            self._current_url = None
            return
        if tag in {"a", "div", "span"} and self._capture_snippet:
            self._capture_snippet = False
            snippet = _normalize_space("".join(self._current_snippet))
            if snippet and self.results:
                latest = self.results[-1]
                self.results[-1] = replace(latest, snippet=snippet)
            self._current_snippet = []

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._current_title.append(data)
        if self._capture_snippet:
            self._current_snippet.append(data)


def _normalize_http_url(value: str) -> str:
    normalized = value.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise WebFetchError("web fetch requires an absolute http or https URL")
    return normalized


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def _normalized_content_type(value: str | None) -> str:
    if value is None:
        return "application/octet-stream"
    return value.split(";", 1)[0].strip().lower() or "application/octet-stream"


def _response_status(response: Any) -> int | None:
    status = getattr(response, "status", None)
    if isinstance(status, int):
        return status
    getter = getattr(response, "getcode", None)
    if callable(getter):
        code = getter()
        if isinstance(code, int):
            return code
    return None
