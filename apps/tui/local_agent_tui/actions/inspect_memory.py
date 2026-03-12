from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InspectMemoryAction:
    task_id: str | None
    run_id: str | None
    origin_screen: str


def build_inspect_memory_action(
    *,
    task_id: str | None,
    run_id: str | None,
    origin_screen: str,
) -> InspectMemoryAction:
    return InspectMemoryAction(task_id=task_id, run_id=run_id, origin_screen=origin_screen)
