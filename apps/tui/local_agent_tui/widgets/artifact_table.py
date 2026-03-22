from __future__ import annotations

from typing import Any

from rich.text import Text

from ..compat import Label, ListItem, ListView, _TEXTUAL_IMPORT_ERROR
from ..store.selectors import ArtifactBrowserRowViewModel
from ._dirty import DirtyCheckMixin


class ArtifactTableGroupHeader(ListItem):  # type: ignore[misc]
    can_focus = False

    def __init__(self, label: str) -> None:
        super().__init__(Label(Text(label, style="bold")))


class ArtifactTableRow(ListItem):  # type: ignore[misc]
    def __init__(self, item: ArtifactBrowserRowViewModel) -> None:
        self.artifact_id = item.artifact_id
        name = _truncate(item.display_name, 28)
        content_type = _truncate(item.content_type_label, 10)
        created = _truncate(item.created_at_relative, 10)
        context = _truncate(item.context_label or item.origin_label, 28)
        marker = "▎" if item.is_selected else ("•" if item.is_highlighted else " ")
        text = Text()
        text.append(f"{marker} {item.icon} ", style="bold")
        text.append(f"{name:<28}", style="bold")
        text.append(f" {content_type:<10}")
        text.append(f" {context:<28}")
        text.append(f" {created:>10}")
        super().__init__(Label(text))


class ArtifactTablePlaceholderRow(ListItem):  # type: ignore[misc]
    def __init__(self, label: str) -> None:
        super().__init__(Label(Text(label)))


class ArtifactTableWidget(DirtyCheckMixin, ListView):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._row_signature: tuple[tuple[str, str, str, str, str, str], ...] = ()

    def update_artifacts(
        self,
        items: list[ArtifactBrowserRowViewModel],
        *,
        focused: bool,
        group_by: str,
    ) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        if not self._should_render((items, focused, group_by), attr_name="_last_render_state"):
            return
        selected_index = None
        signature = tuple(_artifact_row_signature(item) for item in items)
        if signature != self._row_signature:
            self.clear()
            display_index = 0
            for item in items:
                if item.group_header:
                    self.append(ArtifactTableGroupHeader(item.group_header))
                    display_index += 1
                self.append(ArtifactTableRow(item))
                if item.is_selected:
                    selected_index = display_index
                display_index += 1
            self._row_signature = signature
        else:
            display_index = 0
            for index, item in enumerate(items):
                if item.group_header:
                    display_index += 1
                if item.is_selected:
                    selected_index = display_index
                display_index += 1
        if selected_index is not None:
            self.index = selected_index
        self.border_title = f"Artifacts by {group_by}"
        self.border_subtitle = "Icon Name                         Type       Context                       Updated"
        self.set_class(focused, "-focused-pane")

    def show_loading(self, label: str, *, focused: bool, group_by: str) -> None:
        self._reset_render_cache(attr_name="_last_render_state")
        self.clear()
        self.append(ArtifactTablePlaceholderRow(label))
        self.border_title = f"Artifacts by {group_by}"
        self.border_subtitle = "Loading artifacts..."
        self.set_class(focused, "-focused-pane")
        self._row_signature = ()


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return f"{value[: width - 3]}..."


def _artifact_row_signature(item: ArtifactBrowserRowViewModel) -> tuple[str, str, str, str, str, str]:
    return (
        item.artifact_id,
        item.display_name,
        item.content_type,
        item.created_at_relative,
        item.logical_path,
        item.group_label,
    )
