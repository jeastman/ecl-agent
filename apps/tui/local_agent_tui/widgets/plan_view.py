from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rich.markup import escape

from ..store.selectors import PlanViewModel

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


class PlanViewWidget(Static):  # type: ignore[misc]
    def update_plan(self, model: PlanViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Plan"
        lines = [
            f"Phase: {escape(model.current_phase)}",
            "",
            "Current Step",
            escape(model.current_step),
        ]
        if model.recent_updates:
            lines.extend(["", "Recent Updates"])
            lines.extend(
                f"{escape(item.timestamp)}  {escape(item.summary)}"
                for item in model.recent_updates
            )
        self.update("\n".join(lines))
