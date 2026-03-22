from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..compat import ComposeResult, Static, Vertical, _TEXTUAL_IMPORT_ERROR
from ..theme.colors import STATUS_DANGER, STATUS_INFO, STATUS_SUCCESS, STATUS_WARNING


@dataclass(slots=True)
class ToastMessage:
    message: str
    level: str = "info"
    timeout_seconds: float | None = None


class ToastItem(Static):  # type: ignore[misc]
    def update_toast(self, toast: ToastMessage) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        self.update(toast.message)
        self.remove_class("-info", "-success", "-warning", "-error")
        self.add_class(f"-{_toast_level(toast.level)}")


class ToastRack(Vertical):  # type: ignore[misc]
    def compose(self) -> ComposeResult:
        if False:
            yield

    def show_toast(self, toast: ToastMessage) -> None:
        if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover
            raise RuntimeError("textual is required to render the TUI") from _TEXTUAL_IMPORT_ERROR
        item = ToastItem(classes="toast-item")
        item.update_toast(toast)
        self.mount(item)
        timeout = toast.timeout_seconds
        if timeout is not None and timeout > 0:
            self.set_timer(timeout, lambda: self.dismiss_toast(item))

    def dismiss_toast(self, item: ToastItem) -> None:
        if item.parent is self:
            item.remove()


def toast_level_color(level: str) -> str:
    return {
        "info": STATUS_INFO,
        "success": STATUS_SUCCESS,
        "warning": STATUS_WARNING,
        "error": STATUS_DANGER,
    }[_toast_level(level)]


def _toast_level(level: str) -> str:
    normalized = level.strip().lower()
    if normalized in {"success", "warning", "error"}:
        return normalized
    return "info"
