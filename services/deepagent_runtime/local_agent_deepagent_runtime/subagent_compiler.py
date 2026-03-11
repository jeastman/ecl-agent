from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable

from deepagents.middleware.subagents import SubAgent
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse

from apps.runtime.local_agent_runtime.subagents import ResolvedSubagentConfiguration
from packages.protocol.local_agent_protocol.models import utc_now_timestamp
from services.deepagent_runtime.local_agent_deepagent_runtime.prompt_builder import PromptBuilder
from services.deepagent_runtime.local_agent_deepagent_runtime.tool_bindings import (
    SandboxToolBindings,
)

EventCallback = Callable[[str, dict[str, Any]], None]
ModelFactory = Callable[
    [
        str,
    ],
    Any,
]


class SubagentCompilationError(ValueError):
    pass


@dataclass(slots=True)
class SubagentCompiler:
    prompt_builder: PromptBuilder
    model_factory: Callable[..., Any]

    def compile_subagents(
        self,
        *,
        resolved_subagents: list[ResolvedSubagentConfiguration],
        identity_bundle_text: str,
        task_objective: str,
        run_id: str,
        tool_bindings: SandboxToolBindings,
        on_event: EventCallback | None = None,
    ) -> list[SubAgent]:
        compiled: list[SubAgent] = []
        for resolved in resolved_subagents:
            definition = resolved.asset_bundle.definition
            role_tools = tool_bindings.as_langchain_tools(
                resolved.tool_bindings,
                memory_scopes=_normalize_memory_scopes(definition.memory_scope),
                filesystem_scopes=definition.filesystem_scope,
            )
            if not role_tools and resolved.tool_bindings:
                raise SubagentCompilationError(
                    f"Subagent {definition.role_id} resolved tools but none were realizable"
                )
            skill_payloads = _load_skill_payloads(resolved)
            middleware: list[AgentMiddleware] = []
            if on_event is not None:
                middleware.append(
                    _SubagentEventMiddleware(
                        role=definition.role_id,
                        run_id=run_id,
                        task_objective=task_objective,
                        on_event=on_event,
                    )
                )
            compiled.append(
                {
                    "name": definition.role_id,
                    "description": definition.description,
                    "system_prompt": self.prompt_builder.build_subagent_prompt(
                        resolved=resolved,
                        identity_bundle_text=identity_bundle_text,
                    ),
                    "model": self.model_factory(
                        resolved.model_route.model,
                        model_provider=resolved.model_route.provider,
                    ),
                    "tools": role_tools,
                    "skills": skill_payloads,
                    "middleware": middleware,
                }
            )
        return compiled


def _load_skill_payloads(resolved: ResolvedSubagentConfiguration) -> list[str]:
    payloads: list[str] = []
    for descriptor in resolved.skills:
        payload = descriptor.prompt_text.strip()
        if not payload:
            raise SubagentCompilationError(
                f"Subagent skill {descriptor.skill_id} is empty: {descriptor.prompt_path}"
            )
        payloads.append(payload)
    return payloads


def _normalize_memory_scopes(scopes: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for scope in scopes:
        value = scope.strip()
        if value == "run":
            normalized.append("run_state")
        elif value:
            normalized.append(value)
    return tuple(normalized)


class _SubagentEventMiddleware(AgentMiddleware[Any, Any, Any]):
    def __init__(
        self,
        *,
        role: str,
        run_id: str,
        task_objective: str,
        on_event: EventCallback,
    ) -> None:
        super().__init__()
        self.role = role
        self.run_id = run_id
        self.task_objective = task_objective
        self.on_event = on_event
        self._emitted = False
        self._completed = False
        self._started_at: float | None = None

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        if not self._emitted:
            self._started_at = monotonic()
            self.on_event(
                "subagent.started",
                {
                    "runId": self.run_id,
                    "subagentId": self.role,
                    "taskDescription": self.task_objective,
                    "timestamp": utc_now_timestamp(),
                },
            )
            self._emitted = True
        response = handler(request)
        if not self._completed:
            self.on_event(
                "subagent.completed",
                {
                    "runId": self.run_id,
                    "subagentId": self.role,
                    "status": "success",
                    "duration": round(max(monotonic() - (self._started_at or 0.0), 0.0), 6),
                    "timestamp": utc_now_timestamp(),
                },
            )
            self._completed = True
        return response
