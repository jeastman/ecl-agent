from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol, cast

from deepagents import create_deep_agent
from deepagents.middleware.subagents import CompiledSubAgent, SubAgent
from langchain.chat_models import init_chat_model

from apps.runtime.local_agent_runtime.subagents import ResolvedToolBinding
from services.deepagent_runtime.local_agent_deepagent_runtime.prompt_builder import PromptBuilder
from services.deepagent_runtime.local_agent_deepagent_runtime.interrupt_bridge import (
    ApprovalRequiredInterrupt,
    InterruptBridge,
    PolicyDeniedInterrupt,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.subagent_compiler import (
    SubagentCompilationError,
    SubagentCompiler,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.tool_bindings import (
    SandboxToolBindings,
)

if TYPE_CHECKING:
    from apps.runtime.local_agent_runtime.task_runner import (
        AgentExecutionRequest,
        AgentExecutionResult,
    )


EventCallback = Callable[[str, dict[str, Any]], None]


class ModelFactory(Protocol):
    def __call__(self, model_name: str, *, model_provider: str) -> Any: ...


class AgentFactory(Protocol):
    def __call__(
        self,
        *,
        model: Any,
        tools: list[Any],
        system_prompt: str,
        subagents: list[SubAgent | CompiledSubAgent] | None = None,
        name: str,
        **kwargs: Any,
    ) -> "CompiledAgent": ...


class CompiledAgent(Protocol):
    def invoke(
        self, input: dict[str, Any], config: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...


class LangChainDeepAgentHarness:
    def __init__(
        self,
        *,
        model_name: str,
        model_provider: str,
        prompt_builder: PromptBuilder | None = None,
        model_factory: ModelFactory | None = None,
        agent_factory: AgentFactory | None = None,
    ) -> None:
        self._model_name = model_name
        self._model_provider = model_provider
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._model_factory = model_factory or init_chat_model
        self._agent_factory = agent_factory or create_deep_agent
        self._subagent_compiler = SubagentCompiler(
            prompt_builder=self._prompt_builder,
            model_factory=self._model_factory,
        )

    def execute(
        self,
        request: "AgentExecutionRequest",
        on_event: EventCallback | None = None,
    ) -> "AgentExecutionResult":
        from apps.runtime.local_agent_runtime.task_runner import AgentExecutionResult

        callback = on_event or _noop_event
        prompt = self._prompt_builder.build_primary_prompt(
            identity_bundle_text=request.identity_bundle_text,
            workspace_roots=request.workspace_roots,
            objective=request.objective,
            constraints=request.constraints,
            success_criteria=request.success_criteria,
            available_roles=[
                resolved.asset_bundle.definition.role_id for resolved in request.resolved_subagents
            ],
        )
        callback(
            "plan.updated",
            {
                "phase": "planning",
                "summary": "Prepared the primary Deep Agent prompt and resolved role configuration.",
                "prompt_preview": _truncate(prompt, 280),
            },
        )
        callback(
            "subagent.started",
            {
                "role": "primary",
                "name": "primary",
                "summary": "Primary Deep Agent execution started.",
            },
        )
        interrupt_bridge = InterruptBridge(
            governed_operation=request.governed_operation,
            checkpoint_controller=request.checkpoint_controller,
            on_event=callback,
        )
        tools = SandboxToolBindings(
            sandbox=request.sandbox,
            task_id=request.task_id,
            run_id=request.run_id,
            artifact_store=request.artifact_store,
            memory_store=request.memory_store,
            on_event=callback,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=interrupt_bridge.authorize,
        )
        try:
            if request.checkpoint_controller is not None:
                metadata = request.checkpoint_controller.record_checkpoint(
                    "resumed_before_invoke" if request.resume_from_checkpoint_id else "run_started"
                )
                callback("checkpoint.saved", metadata.to_dict())
            summary, artifact_paths = self._run_agent_task(request, tools, prompt, callback)
            if request.checkpoint_controller is not None:
                metadata = request.checkpoint_controller.record_checkpoint("run_completed")
                callback("checkpoint.saved", metadata.to_dict())
            return AgentExecutionResult(
                success=True,
                summary=summary,
                output_artifacts=artifact_paths,
            )
        except ApprovalRequiredInterrupt as exc:
            return AgentExecutionResult(
                success=False,
                summary=exc.summary,
                output_artifacts=[],
                paused=True,
                pause_reason="awaiting approval",
                awaiting_approval=True,
                pending_approval_id=exc.approval_id,
            )
        except PolicyDeniedInterrupt as exc:
            return AgentExecutionResult(
                success=False,
                summary=exc.reason,
                output_artifacts=[],
                error_message=exc.reason,
                failure_code="policy_denied",
            )
        except (SubagentCompilationError, PermissionError, ValueError) as exc:
            return AgentExecutionResult(
                success=False,
                summary="Agent harness failed during Deep Agent execution.",
                output_artifacts=[],
                error_message=str(exc),
            )
        except Exception as exc:
            return AgentExecutionResult(
                success=False,
                summary="Agent harness failed during Deep Agent execution.",
                output_artifacts=[],
                error_message=str(exc),
            )

    def _run_agent_task(
        self,
        request: "AgentExecutionRequest",
        tools: SandboxToolBindings,
        prompt: str,
        callback: EventCallback,
    ) -> tuple[str, list[str]]:
        model = self._model_factory(
            self._model_name,
            model_provider=self._model_provider,
        )
        compiled_subagents = self._subagent_compiler.compile_subagents(
            resolved_subagents=request.resolved_subagents,
            identity_bundle_text=request.identity_bundle_text,
            tool_bindings=tools,
            on_event=callback,
        )
        subagents_for_agent = cast(
            list[SubAgent | CompiledSubAgent] | None,
            compiled_subagents or None,
        )
        primary_tools = tools.as_langchain_tools(
            _primary_tool_bindings(),
            memory_scopes=("project", "run_state", "identity"),
        )
        agent = self._agent_factory(
            model=model,
            tools=primary_tools,
            system_prompt=prompt,
            subagents=subagents_for_agent,
            name="primary",
            **(
                request.checkpoint_controller.build_agent_kwargs()
                if request.checkpoint_controller is not None
                else {}
            ),
        )
        callback(
            "plan.updated",
            {
                "phase": "executing",
                "summary": "Executing the primary Deep Agent with compiled project-owned subagents.",
            },
        )
        result = _invoke_agent(
            agent,
            {"messages": [{"role": "user", "content": _execution_prompt(request)}]},
            config=(
                request.checkpoint_controller.build_invoke_config()
                if request.checkpoint_controller is not None
                else None
            ),
        )
        summary = _extract_summary(result)
        return summary, tools.written_paths


def _primary_tool_bindings() -> tuple[ResolvedToolBinding, ...]:
    return (
        ResolvedToolBinding(
            tool_id="read_files",
            capability_aliases=("read_file", "filesystem", "files.read"),
            requires_policy=True,
        ),
        ResolvedToolBinding(
            tool_id="write_files",
            capability_aliases=("write_file", "filesystem", "files.write"),
            requires_policy=True,
        ),
        ResolvedToolBinding(
            tool_id="execute_commands",
            capability_aliases=("execute_command", "commands", "sandbox.execute"),
            requires_policy=True,
        ),
        ResolvedToolBinding(
            tool_id="memory_lookup",
            capability_aliases=("memory_lookup", "memory", "memory.read"),
            requires_policy=False,
        ),
        ResolvedToolBinding(
            tool_id="plan_update",
            capability_aliases=("plan_update", "planning", "plan.write"),
            requires_policy=False,
        ),
        ResolvedToolBinding(
            tool_id="artifact_inspect",
            capability_aliases=("artifact_inspect", "artifacts", "artifacts.read"),
            requires_policy=False,
        ),
    )


def _execution_prompt(request: "AgentExecutionRequest") -> str:
    sections = [
        request.objective.strip(),
        "",
        "Complete the objective using governed tools and native Deep Agent delegation when it improves focus or isolation.",
    ]
    if request.constraints:
        sections.extend(["", "Constraints:"])
        sections.extend(f"- {item}" for item in request.constraints if item.strip())
    if request.success_criteria:
        sections.extend(["", "Success Criteria:"])
        sections.extend(f"- {item}" for item in request.success_criteria if item.strip())
    return "\n".join(sections).strip()


def _noop_event(_: str, __: dict[str, Any]) -> None:
    return None


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def _extract_summary(result: dict[str, Any]) -> str:
    messages = result.get("messages", [])
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return _truncate(content.strip(), 280)
        if isinstance(message, dict):
            dict_content = message.get("content")
            if isinstance(dict_content, str) and dict_content.strip():
                return _truncate(dict_content.strip(), 280)
    return "Deep Agent execution completed."


def _invoke_agent(
    agent: Any, payload: dict[str, Any], config: dict[str, Any] | None
) -> dict[str, Any]:
    if config is None:
        return agent.invoke(payload)
    try:
        return agent.invoke(payload, config=config)
    except TypeError:
        return agent.invoke(payload)
