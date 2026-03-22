from __future__ import annotations

from typing import Any

_MISSING = object()


class DirtyCheckMixin:
    def _should_render(self, model: Any, *, attr_name: str = "_last_model") -> bool:
        previous = getattr(self, attr_name, _MISSING)
        if previous == model:
            return False
        setattr(self, attr_name, model)
        return True

    def _reset_render_cache(self, *, attr_name: str = "_last_model") -> None:
        setattr(self, attr_name, _MISSING)
