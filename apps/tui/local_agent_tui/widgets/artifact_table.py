from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.text import Text

from ..store.selectors import ArtifactBrowserRowViewModel

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.widgets import Label, ListItem, ListView
else:  # pragma: no cover
    try:
        from textual.widgets import Label, ListItem, ListView
    except ModuleNotFoundError as exc:
        Label = cast(Any, object)
        ListItem = cast(Any, object)
        ListView = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class ArtifactTableRow(ListItem):  # type: ignore[misc]
    def __init__(self, item: ArtifactBrowserRowViewModel) -> None:
        self.artifact_id = item.artifact_id
        name = _truncate(item.display_name, 26)
        content_type = _truncate(item.content_type, 18)
        created = _truncate(item.created_at, 20)
        origin = _truncate(f"{item.task_id}/{item.run_id}", 18)
        group = _truncate(item.group_label, 18)
        marker = "*" if item.is_highlighted else " "
        text = Text()
        text.append(f"{marker} {name:<26} {content_type:<18} {created:<20} {origin:<18}")
        text.append("\n")
        text.append(f"  Group: {group}  Path: {_truncate(item.logical_path, 52)}")
        super().__init__(Label(text))


class ArtifactTablePlaceholderRow(ListItem):  # type: ignore[misc]
    def __init__(self, label: str) -> None:
        super().__init__(Label(Text(label)))


class ArtifactTableWidget(ListView):  # type: ignore[misc]
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
        selected_index = None
        signature = tuple(_artifact_row_signature(item) for item in items)
        if signature != self._row_signature:
            self.clear()
            for index, item in enumerate(items):
                self.append(ArtifactTableRow(item))
                if item.is_selected:
                    selected_index = index
            self._row_signature = signature
        else:
            for index, item in enumerate(items):
                if item.is_selected:
                    selected_index = index
        if selected_index is not None:
            self.index = selected_index
        self.border_title = f"Artifacts by {group_by}"
        self.border_subtitle = (
            "Name                       Type               Created              Task/Run"
        )
        self.set_class(focused, "-focused-pane")

    def show_loading(self, label: str, *, focused: bool, group_by: str) -> None:
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
        item.created_at,
        item.logical_path,
        item.group_label,
    )
