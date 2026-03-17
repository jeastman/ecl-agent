from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class WebDocument:
    url: str
    final_url: str
    title: str | None
    markdown_content: str
    fetched_at: str
    content_type: str
    status_code: int | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    rank: int
    source: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class WebFetchError(ValueError):
    pass


class WebSearchError(ValueError):
    pass
