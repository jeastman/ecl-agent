from __future__ import annotations

from typing import Protocol

from services.web_service.local_agent_web_service.models import WebDocument, WebSearchResult


class WebFetchPort(Protocol):
    def fetch(
        self,
        url: str,
        *,
        max_bytes: int | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
    ) -> WebDocument: ...


class WebSearchPort(Protocol):
    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        locale: str | None = None,
    ) -> list[WebSearchResult]: ...
