from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..store.selectors import TaskActionBarViewModel

_TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

if TYPE_CHECKING:
    from textual.widgets import Static
else:  # pragma: no cover
    try:
        from textual.widgets import Static
    except ModuleNotFoundError as exc:
        Static = cast(Any, object)
        _TEXTUAL_IMPORT_ERROR = exc
    else:
        _TEXTUAL_IMPORT_ERROR = None


class InputBoxWidget(Static):  # type: ignore[misc]
    def update_actions(self, model: TaskActionBarViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Input / Actions"
        hints: list[str] = []
        if model.resume_enabled:
            hints.append("[R] Resume")
        if model.approvals_enabled:
            hints.append("[A] Approvals")
        if model.artifact_open_enabled:
            hints.append("[O] Artifact")
        if model.back_enabled:
            hints.append("[Esc] Back")
        self.update(f"{model.command_text}\n\n{'   '.join(hints)}")
