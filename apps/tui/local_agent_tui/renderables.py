from __future__ import annotations

from collections.abc import Iterable, Sequence

from rich.console import Group, RenderableType
from rich.text import Text

from .theme.colors import TEXT_MUTED, TEXT_SECONDARY


def text(value: str, *, style: str | None = None) -> Text:
    return Text(value, style=style)


def badge(
    label: str,
    *,
    style: str | None = None,
    prefix: str = "",
    suffix: str = "",
) -> Text:
    rendered = Text()
    if prefix:
        rendered.append(prefix)
    rendered.append(label, style=style)
    if suffix:
        rendered.append(suffix)
    return rendered


def muted(value: str) -> Text:
    return text(value, style=TEXT_MUTED)


def join(parts: Sequence[str | Text], *, separator: str = "   ") -> Text:
    rendered = Text()
    for index, part in enumerate(parts):
        if index:
            rendered.append(separator)
        rendered.append_text(_coerce_text(part))
    return rendered


def key_hints(hints: Sequence[str]) -> Text:
    return join([muted(hint) for hint in hints])


def metadata_line(pairs: Sequence[tuple[str, str]], *, separator: str = "   ") -> Text:
    rendered = Text()
    for index, (label, value) in enumerate(pairs):
        if index:
            rendered.append(separator)
        rendered.append(f"{label}: ", style=TEXT_MUTED)
        rendered.append(value)
    return rendered


def divider(width: int, *, style: str = TEXT_SECONDARY) -> Text:
    return Text("─" * max(4, width), style=style)


def section(title: str, body: str | Text | RenderableType) -> Group:
    return Group(text(title, style="bold"), body)


def block(lines: Iterable[str | Text | RenderableType]) -> Group:
    renderables: list[RenderableType] = []
    for line in lines:
        if isinstance(line, Text):
            renderables.append(line)
        elif isinstance(line, str):
            renderables.append(text(line))
        else:
            renderables.append(line)
    return Group(*renderables)


def highlighted_row(content: str | Text, *, highlighted: bool) -> Text:
    rendered = _coerce_text(content)
    if highlighted:
        rendered.stylize("reverse")
    return rendered


def _coerce_text(value: str | Text) -> Text:
    if isinstance(value, Text):
        return value.copy()
    return text(value)
