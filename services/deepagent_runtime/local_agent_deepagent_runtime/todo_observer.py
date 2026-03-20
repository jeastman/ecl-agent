from __future__ import annotations

from typing import Any, Callable

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
from langchain_core.messages import AIMessage
from langgraph.types import Command
from packages.task_model.local_agent_task_model.models import normalize_todos

EventCallback = Callable[[str, dict[str, Any]], None]


class TodoStateObserverMiddleware(AgentMiddleware[Any, Any, Any]):
    def __init__(self, on_event: EventCallback) -> None:
        self._on_event = on_event

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any] | AIMessage:
        return handler(request)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ) -> Any:
        result = handler(request)
        if request.tool_call.get("name") != "write_todos":
            return result
        next_todos = _todos_from_command(result)
        if next_todos is None:
            return result
        previous_todos = _todos_from_state(request.state)
        if previous_todos == next_todos:
            return result
        counts = _todo_counts(next_todos)
        self._on_event(
            "tool.called",
            {
                "tool": "write_todos",
                "arguments": {"todos": next_todos},
                "summary": (
                    "Updated todo list "
                    f"({counts['todo_count']} items; "
                    f"{counts['in_progress_count']} in progress, "
                    f"{counts['pending_count']} pending, "
                    f"{counts['completed_count']} completed)"
                ),
                **counts,
            },
        )
        return result


def _todos_from_state(state: Any) -> list[dict[str, str]]:
    if not isinstance(state, dict):
        return []
    return [todo.to_dict() for todo in normalize_todos(state.get("todos"))]


def _todos_from_command(result: Any) -> list[dict[str, str]] | None:
    if not isinstance(result, Command):
        return None
    update = getattr(result, "update", None)
    if not isinstance(update, dict) or "todos" not in update:
        return None
    return [todo.to_dict() for todo in normalize_todos(update.get("todos"))]


def _todo_counts(todos: list[dict[str, str]]) -> dict[str, int]:
    completed = sum(1 for todo in todos if todo["status"] == "completed")
    in_progress = sum(1 for todo in todos if todo["status"] == "in_progress")
    pending = sum(1 for todo in todos if todo["status"] == "pending")
    return {
        "todo_count": len(todos),
        "completed_count": completed,
        "in_progress_count": in_progress,
        "pending_count": pending,
    }
