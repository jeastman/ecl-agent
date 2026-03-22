from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical, VerticalScroll
    from textual.css.query import NoMatches
    from textual.events import Key
    from textual.screen import ModalScreen, Screen
    from textual.widget import Widget as _Widget
    from textual.widgets import Button, Input, Label, ListItem, ListView, Markdown, Static, TextArea
else:  # pragma: no cover
    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Container, Horizontal, Vertical, VerticalScroll
        from textual.css.query import NoMatches
        from textual.events import Key
        from textual.screen import ModalScreen, Screen
        from textual.widget import Widget as _Widget
        from textual.widgets import (
            Button,
            Input,
            Label,
            ListItem,
            ListView,
            Markdown,
            Static,
            TextArea,
        )
    except ModuleNotFoundError as exc:
        App = cast(Any, object)
        ComposeResult = cast(Any, object)
        Binding = cast(Any, object)
        Container = cast(Any, object)
        Horizontal = cast(Any, object)
        Vertical = cast(Any, object)
        VerticalScroll = cast(Any, object)
        NoMatches = cast(Any, RuntimeError)
        Key = cast(Any, object)
        ModalScreen = cast(Any, object)
        Screen = cast(Any, object)
        _Widget = cast(Any, object)
        Button = cast(Any, object)
        Input = cast(Any, object)
        Label = cast(Any, object)
        ListItem = cast(Any, object)
        ListView = cast(Any, object)
        Markdown = cast(Any, object)
        Static = cast(Any, object)
        TextArea = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


def ensure_textual() -> None:
    if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
        raise RuntimeError("textual is required to run the TUI") from _TEXTUAL_IMPORT_ERROR
