from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from deepagents.middleware.subagents import SubAgent
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse

from apps.runtime.local_agent_runtime.subagents import ResolvedSubagentConfiguration
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
        tool_bindings: SandboxToolBindings,
        on_event: EventCallback | None = None,
    ) -> list[SubAgent]:
        compiled: list[SubAgent] = []
        for resolved in resolved_subagents:
            definition = resolved.asset_bundle.definition
            role_tools = tool_bindings.as_langchain_tools(
                resolved.tool_bindings,
                memory_scopes=_normalize_memory_scopes(definition.memory_scope),
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
                        agent_name=definition.name,
                        model_profile=resolved.model_route.profile_name,
                        objective=task_objective,
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
        try:
            payload = descriptor.prompt_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SubagentCompilationError(
                f"Unable to read subagent skill {descriptor.skill_id}: {descriptor.prompt_path}"
            ) from exc
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
        agent_name: str,
        model_profile: str,
        objective: str,
        on_event: EventCallback,
    ) -> None:
        super().__init__()
        self.role = role
        self.agent_name = agent_name
        self.model_profile = model_profile
        self.objective = objective
        self.on_event = on_event
        self._emitted = False
        self._completed = False

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        if not self._emitted:
            self.on_event(
                "subagent.started",
                {
                    "role": self.role,
                    "model_profile": self.model_profile,
                    "objective": self.objective,
                },
            )
            self._emitted = True
        response = handler(request)
        if not self._completed:
            self.on_event(
                "subagent.completed",
                {
                    "role": self.role,
                    "summary": f"{self.agent_name} completed delegated execution.",
                    "outcome": "success",
                },
            )
            self._completed = True
        return response
