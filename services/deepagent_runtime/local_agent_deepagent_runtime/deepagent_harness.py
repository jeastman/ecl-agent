from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from services.deepagent_runtime.local_agent_deepagent_runtime.prompt_builder import PromptBuilder
from services.deepagent_runtime.local_agent_deepagent_runtime.interrupt_bridge import (
    ApprovalRequiredInterrupt,
    InterruptBridge,
    PolicyDeniedInterrupt,
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

    def execute(
        self,
        request: "AgentExecutionRequest",
        on_event: EventCallback | None = None,
    ) -> "AgentExecutionResult":
        from apps.runtime.local_agent_runtime.task_runner import AgentExecutionResult

        callback = on_event or _noop_event
        prompt = self._prompt_builder.build_system_prompt(
            identity_bundle_text=request.identity_bundle_text,
            workspace_roots=request.workspace_roots,
            objective=request.objective,
            constraints=request.constraints,
            success_criteria=request.success_criteria,
        )
        callback(
            "plan.updated",
            {
                "phase": "planning",
                "summary": "Survey the governed workspace and generate the reference summary artifact.",
                "prompt_preview": _truncate(prompt, 280),
            },
        )
        callback(
            "subagent.started",
            {
                "role": "primary",
                "name": "repo-summarizer",
                "summary": "Primary single-agent execution started.",
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
            artifact_path, summary = self._run_reference_task(request, tools, prompt, callback)
            if request.checkpoint_controller is not None:
                metadata = request.checkpoint_controller.record_checkpoint("run_completed")
                callback("checkpoint.saved", metadata.to_dict())
            return AgentExecutionResult(
                success=True,
                summary=summary,
                output_artifacts=[artifact_path],
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
        except Exception as exc:
            return AgentExecutionResult(
                success=False,
                summary="Agent harness failed during reference task execution.",
                output_artifacts=[],
                error_message=str(exc),
            )

    def _run_reference_task(
        self,
        request: "AgentExecutionRequest",
        tools: SandboxToolBindings,
        prompt: str,
        callback: EventCallback,
    ) -> tuple[str, str]:
        model = self._model_factory(
            self._model_name,
            model_provider=self._model_provider,
        )
        # We intentionally pass sandbox-backed LangChain tools instead of the built-in
        # DeepAgent filesystem backend so all file and command access still flows through
        # the project-owned ExecutionSandbox boundary.
        agent = self._agent_factory(
            model=model,
            tools=tools.as_langchain_tools(),
            system_prompt=prompt,
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
                "summary": "Executing the DeepAgent reference task inside the governed sandbox.",
            },
        )
        result = _invoke_agent(
            agent,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": _reference_task_prompt(request.objective),
                    }
                ]
            },
            config=(
                request.checkpoint_controller.build_invoke_config()
                if request.checkpoint_controller is not None
                else None
            ),
        )
        artifact_path = "workspace/artifacts/repo_summary.md"
        if not request.sandbox.exists(artifact_path):
            raise RuntimeError(
                "DeepAgent run completed without creating workspace/artifacts/repo_summary.md"
            )
        summary = _extract_summary(result)
        return artifact_path, summary


def _noop_event(_: str, __: dict[str, Any]) -> None:
    return None


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def _reference_task_prompt(objective: str) -> str:
    return "\n".join(
        [
            objective,
            "",
            "Inspect the governed repository workspace and produce a Markdown architecture summary.",
            "Use only sandbox-backed tools.",
            "Write the final artifact to workspace/artifacts/repo_summary.md.",
            "The summary should cover runtime ownership, sandbox mediation, adapter isolation, and major repository packages.",
        ]
    )


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
    return "Generated artifacts/repo_summary.md from the governed workspace."


def _invoke_agent(
    agent: Any, payload: dict[str, Any], config: dict[str, Any] | None
) -> dict[str, Any]:
    if config is None:
        return agent.invoke(payload)
    try:
        return agent.invoke(payload, config=config)
    except TypeError:
        return agent.invoke(payload)
