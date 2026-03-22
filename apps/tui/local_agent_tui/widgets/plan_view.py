from __future__ import annotations

from rich.console import Group
from rich.text import Text

from ..compat import Static, _TEXTUAL_IMPORT_ERROR
from ..renderables import divider
from ..store.selectors import PlanViewModel
from ..theme.colors import TEXT_PRIMARY, TEXT_SECONDARY
from ..theme.empty_states import render_empty_state
from ..theme.typography import label, title, value
from ._dirty import DirtyCheckMixin


class PlanViewWidget(DirtyCheckMixin, Static):  # type: ignore[misc]
    def update_plan(self, model: PlanViewModel) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.border_title = "Plan"
        if not self._should_render(model):
            return
        if model.current_phase == "unknown" and model.current_step == "No task selected.":
            self.update(render_empty_state("plan"))
            return
        lines: list[Text] = []
        phase_row = Text()
        phase_row.append_text(label("Phase  "))
        phase_row.append_text(value(model.current_phase))
        lines.append(phase_row)
        lines.append(divider(self.content_size.width - 2, style=TEXT_SECONDARY))
        lines.append(title("Current Step"))
        lines.append(Text(model.current_step, style=TEXT_PRIMARY))
        if model.recent_updates:
            lines.extend([Text(""), title("Recent Updates")])
            lines.extend(
                Text(f"{item.timestamp_display}  {item.summary}", style=TEXT_SECONDARY)
                for item in model.recent_updates
            )
        self.update(Group(*lines))
