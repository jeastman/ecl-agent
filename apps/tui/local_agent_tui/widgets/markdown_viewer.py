from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from ..store.selectors import MarkdownArtifactViewModel

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import VerticalScroll
    from textual.widgets import Markdown
else:  # pragma: no cover
    try:
        from textual.app import ComposeResult
        from textual.containers import VerticalScroll
        from textual.widgets import Markdown
    except ModuleNotFoundError as exc:
        ComposeResult = cast(Any, object)
        VerticalScroll = cast(Any, object)
        Markdown = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


@dataclass(frozen=True, slots=True)
class MarkdownSearchState:
    query: str = ""
    current_match: int = 0
    total_matches: int = 0


class MarkdownViewerWidget(VerticalScroll):  # type: ignore[misc]
    can_focus = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._source_text = ""
        self._search_query = ""
        self._match_lines: list[int] = []
        self._match_index = -1
        self._artifact_signature: tuple[str | None, str] = (None, "")

    def compose(self) -> ComposeResult:
        yield Markdown("", id="markdown-viewer-document")

    def update_markdown(self, model: MarkdownArtifactViewModel | None) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        document = self.query_one("#markdown-viewer-document", Markdown)
        if model is None:
            self.border_title = "Markdown Viewer"
            if self._artifact_signature == (None, ""):
                return
            self._source_text = ""
            self._clear_search()
            self._artifact_signature = (None, "")
            document.update("No markdown artifact selected.")
            self.scroll_to_home()
            return
        self.border_title = model.display_name
        signature = (model.artifact_id, model.body)
        if self._artifact_signature == signature:
            return
        self._source_text = model.body
        self._clear_search()
        self._artifact_signature = signature
        document.update(model.body)
        self.scroll_to_home()

    def scroll_line(self, delta: int) -> None:
        next_y = max(0.0, min(self.max_scroll_y, self.scroll_y + delta))
        self.scroll_to(y=next_y, animate=False, immediate=True)

    def scroll_to_home(self) -> None:
        self.scroll_to(y=0, animate=False, immediate=True)

    def scroll_to_end(self) -> None:
        self.scroll_to(y=self.max_scroll_y, animate=False, immediate=True)

    def begin_search(self, query: str) -> MarkdownSearchState:
        normalized = query.strip()
        self._search_query = normalized
        self._match_lines = self._match_line_numbers(normalized)
        self._match_index = 0 if self._match_lines else -1
        self._scroll_to_current_match()
        return self.search_state

    def find_next(self) -> MarkdownSearchState:
        if not self._match_lines:
            return self.search_state
        self._match_index = (self._match_index + 1) % len(self._match_lines)
        self._scroll_to_current_match()
        return self.search_state

    @property
    def search_state(self) -> MarkdownSearchState:
        if not self._match_lines or self._match_index < 0:
            return MarkdownSearchState(query=self._search_query)
        return MarkdownSearchState(
            query=self._search_query,
            current_match=self._match_index + 1,
            total_matches=len(self._match_lines),
        )

    def _clear_search(self) -> None:
        self._search_query = ""
        self._match_lines = []
        self._match_index = -1

    def _match_line_numbers(self, query: str) -> list[int]:
        if not query:
            return []
        normalized_query = query.casefold()
        matches: list[int] = []
        for line_number, line in enumerate(self._source_text.splitlines() or [self._source_text]):
            if normalized_query in line.casefold():
                matches.append(line_number)
        return matches

    def _scroll_to_current_match(self) -> None:
        if self._match_index < 0 or self._match_index >= len(self._match_lines):
            return
        self.scroll_to(y=self._match_lines[self._match_index], animate=False, immediate=True)

    def on_key(self, event: Any) -> None:
        screen = getattr(self, "screen", None)
        if screen is None:
            return
        key = getattr(event, "key", "")
        if key == "j":
            self.scroll_line(1)
            event.stop()
        elif key == "k":
            self.scroll_line(-1)
            event.stop()
        elif key == "g":
            self.scroll_to_home()
            event.stop()
        elif key in {"G", "shift+g"}:
            self.scroll_to_end()
            event.stop()
        elif key == "/":
            action = getattr(screen, "action_show_search", None)
            if callable(action):
                action()
                event.stop()
        elif key == "q":
            action = getattr(screen, "action_close_viewer", None)
            if callable(action):
                action()
                event.stop()
