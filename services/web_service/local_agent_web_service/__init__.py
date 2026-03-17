from services.web_service.local_agent_web_service.adapters import (
    DuckDuckGoSearchAdapter,
    SimpleMarkdownWebFetchAdapter,
)
from services.web_service.local_agent_web_service.models import (
    WebDocument,
    WebFetchError,
    WebSearchError,
    WebSearchResult,
)
from services.web_service.local_agent_web_service.ports import WebFetchPort, WebSearchPort

__all__ = [
    "DuckDuckGoSearchAdapter",
    "SimpleMarkdownWebFetchAdapter",
    "WebDocument",
    "WebFetchError",
    "WebFetchPort",
    "WebSearchError",
    "WebSearchPort",
    "WebSearchResult",
]
