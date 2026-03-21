from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Protocol, cast

from deepagents import create_deep_agent
from deepagents.middleware.subagents import CompiledSubAgent, SubAgent
from langchain.chat_models import init_chat_model
from langchain_core.exceptions import ContextOverflowError

from apps.runtime.local_agent_runtime.subagents import ResolvedToolBinding, SkillDescriptor
from packages.config.local_agent_config.models import CompactionConfig, MCPConfig
from packages.task_model.local_agent_task_model.models import (
    RecoverableToolRejectionThresholdExceeded,
    RemoteMCPActionState,
    RemoteMCPAuthorizationState,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.compaction_strategy import (
    CompactionStrategyPort,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.prompt_builder import PromptBuilder
from services.deepagent_runtime.local_agent_deepagent_runtime.interrupt_bridge import (
    ApprovalRequiredInterrupt,
    CancellationRequestedInterrupt,
    ClarificationRequiredInterrupt,
    InterruptBridge,
    PolicyDeniedInterrupt,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.todo_observer import (
    TodoStateObserverMiddleware,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.subagent_compiler import (
    SubagentCompilationError,
    SubagentCompiler,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.mcp_provider import (
    MCPToolProvider,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.tool_bindings import SandboxToolBindings
from services.remote_mcp_auth_service import (
    AuthorizationRequiredError,
    RemoteMCPConnectionResolver,
)
from services.remote_mcp_auth_service.local_agent_remote_mcp_auth_service.models import (
    RemoteMCPAuthorizationState as ProviderRemoteMCPAuthorizationState,
)
from services.web_service.local_agent_web_service.ports import WebFetchPort, WebSearchPort

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
        skills: list[str] | None = None,
        name: str,
        **kwargs: Any,
    ) -> "CompiledAgent": ...


class CompiledAgent(Protocol):
    def invoke(
        self, input: dict[str, Any], config: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...


@dataclass(slots=True)
class _CompletedAgentOutcome:
    success: bool
    summary: str
    artifact_paths: list[str]
    error_message: str | None = None
    final_response: str | None = None


class LangChainDeepAgentHarness:
    def __init__(
        self,
        *,
        model_name: str,
        model_provider: str,
        mcp_config: MCPConfig | None = None,
        web_fetch_port: WebFetchPort | None = None,
        web_search_port: WebSearchPort | None = None,
        compaction_policy: CompactionConfig | None = None,
        compaction_strategy: CompactionStrategyPort | None = None,
        prompt_builder: PromptBuilder | None = None,
        model_factory: ModelFactory | None = None,
        agent_factory: AgentFactory | None = None,
        remote_mcp_connection_resolver: RemoteMCPConnectionResolver | None = None,
    ) -> None:
        self._model_name = model_name
        self._model_provider = model_provider
        self._mcp_config = mcp_config or MCPConfig()
        self._web_fetch_port = web_fetch_port
        self._web_search_port = web_search_port
        self._compaction_policy = compaction_policy or CompactionConfig()
        self._compaction_strategy = compaction_strategy
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._model_factory = model_factory or init_chat_model
        self._agent_factory = agent_factory or create_deep_agent
        self._remote_mcp_connection_resolver = (
            remote_mcp_connection_resolver or RemoteMCPConnectionResolver()
        )
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
        interrupt_bridge = InterruptBridge(
            governed_operation=request.governed_operation,
            checkpoint_controller=request.checkpoint_controller,
            on_event=callback,
            cancellation_probe=request.cancellation_probe,
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
            skill_install_handler=request.skill_install_handler,
            user_input_handler=interrupt_bridge.request_user_input,
            web_fetch_port=self._web_fetch_port,
            web_search_port=self._web_search_port,
            interrupt_handler=lambda: interrupt_bridge.raise_if_cancelled("cancel_requested"),
        )
        try:
            interrupt_bridge.raise_if_cancelled("cancel_requested")
            if request.checkpoint_controller is not None:
                metadata = request.checkpoint_controller.record_checkpoint(
                    "resumed_before_invoke" if request.resume_from_checkpoint_id else "run_started"
                )
                callback("checkpoint.saved", metadata.to_dict())
            outcome = self._run_agent_task(request, tools, prompt, callback, interrupt_bridge)
            interrupt_bridge.raise_if_cancelled("cancel_requested")
            if outcome.success and request.checkpoint_controller is not None:
                metadata = request.checkpoint_controller.record_checkpoint("run_completed")
                callback("checkpoint.saved", metadata.to_dict())
            return AgentExecutionResult(
                success=outcome.success,
                summary=outcome.summary,
                output_artifacts=outcome.artifact_paths,
                error_message=outcome.error_message,
                assistant_response=outcome.final_response,
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
        except ClarificationRequiredInterrupt as exc:
            return AgentExecutionResult(
                success=False,
                summary=exc.question,
                output_artifacts=[],
                paused=True,
                pause_reason="awaiting_user_input",
                requested_user_input=exc.question,
            )
        except CancellationRequestedInterrupt as exc:
            return AgentExecutionResult(
                success=False,
                summary="Run interrupted by cancel request.",
                output_artifacts=[],
                paused=True,
                pause_reason="cancel_requested",
                cancelled=True,
                checkpoint_id=exc.checkpoint_id,
            )
        except PolicyDeniedInterrupt as exc:
            return AgentExecutionResult(
                success=False,
                summary=exc.reason,
                output_artifacts=[],
                error_message=exc.reason,
                failure_code="policy_denied",
            )
        except AuthorizationRequiredError as exc:
            return AgentExecutionResult(
                success=False,
                summary=exc.state.summary,
                output_artifacts=[],
                paused=True,
                pause_reason="remote_mcp_authorization_required",
                remote_mcp_authorizations=[
                    _task_remote_mcp_state(exc.state),
                ],
            )
        except RecoverableToolRejectionThresholdExceeded as exc:
            return AgentExecutionResult(
                success=False,
                summary=exc.summary,
                output_artifacts=[],
                error_message=str(exc),
                failure_code="recoverable_rejection_threshold_exceeded",
            )
        except ContextOverflowError as exc:
            return AgentExecutionResult(
                success=False,
                summary="Agent harness failed during Deep Agent execution.",
                output_artifacts=[],
                error_message=str(exc),
                failure_code="compaction_failed",
            )
        except (SubagentCompilationError, PermissionError, ValueError) as exc:
            return AgentExecutionResult(
                success=False,
                summary="Agent harness failed during Deep Agent execution.",
                output_artifacts=[],
                error_message=str(exc),
            )
        except Exception as exc:
            if _is_resumable_transient_execution_error(exc, request):
                return AgentExecutionResult(
                    success=False,
                    summary="Execution paused after a transient upstream error. Resume from the latest checkpoint.",
                    output_artifacts=[],
                    error_message=str(exc),
                    paused=True,
                    pause_reason="awaiting resume",
                )
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
        interrupt_bridge: InterruptBridge,
    ) -> _CompletedAgentOutcome:
        model = self._model_factory(
            self._model_name,
            model_provider=self._model_provider,
        )
        interrupt_bridge.raise_if_cancelled("cancel_requested")
        mcp_provider = MCPToolProvider(
            config=self._mcp_config,
            task_id=request.task_id,
            run_id=request.run_id,
            runtime_user_id=request.runtime_user_id,
            allowed_capabilities=request.allowed_capabilities,
            governed_operation=interrupt_bridge.authorize,
            on_event=callback,
            connection_resolver=self._remote_mcp_connection_resolver,
        )
        mcp_provider.start()
        compiled_subagents = self._subagent_compiler.compile_subagents(
            resolved_subagents=request.resolved_subagents,
            identity_bundle_text=request.identity_bundle_text,
            delegation_description=_delegation_description(request.objective),
            run_id=request.run_id,
            tool_bindings=tools,
            mcp_tools_by_role=mcp_provider.tools_for_role,
            on_event=callback,
        )
        subagents_for_agent = cast(
            list[SubAgent | CompiledSubAgent] | None,
            compiled_subagents or None,
        )
        primary_tools = tools.as_langchain_tools(
            _primary_tool_bindings(),
            memory_scopes=("project", "run_state", "identity"),
            filesystem_scopes=("workspace",),
        )
        primary_tools.extend(mcp_provider.tools_for_role("primary"))
        try:
            interrupt_bridge.raise_if_cancelled("cancel_requested")
            middleware = [TodoStateObserverMiddleware(callback)]
            if self._compaction_strategy is not None and self._compaction_policy.enabled:
                middleware.extend(
                    self._compaction_strategy.build_middleware(
                        model=model,
                        policy=self._compaction_policy,
                        on_compaction=callback,
                    )
                )
            agent = self._agent_factory(
                model=model,
                tools=primary_tools,
                system_prompt=prompt,
                subagents=subagents_for_agent,
                skills=_skill_payloads(request.primary_skills),
                name="primary",
                # create_deep_agent prepends its own default middleware stack,
                # including TodoListMiddleware, so adapter-owned middleware stays
                # additive here instead of duplicating that baseline behavior.
                middleware=middleware,
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
            interrupt_bridge.raise_if_cancelled("cancel_requested")
            result = _invoke_agent(
                agent,
                {"messages": _conversation_payload(request)},
                config=(
                    request.checkpoint_controller.build_invoke_config()
                    if request.checkpoint_controller is not None
                    else None
                ),
            )
            interrupt_bridge.raise_if_cancelled("cancel_requested")
            summary = _extract_summary(result)
            artifact_paths = list(tools.written_paths)
            final_response = _extract_final_assistant_response(result)
            final_response_artifact_path = _write_final_response_artifact(
                request=request,
                final_response=final_response,
            )
            if final_response_artifact_path is not None:
                artifact_paths.append(final_response_artifact_path)
            success = bool(result.get("success", True))
            error_message = _extract_error_message(result)
            return _CompletedAgentOutcome(
                success=success,
                summary=summary,
                artifact_paths=artifact_paths,
                error_message=error_message if not success else None,
                final_response=final_response,
            )
        finally:
            mcp_provider.close()


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
            tool_id="memory_write",
            capability_aliases=("memory_write", "memory", "memory.write"),
            requires_policy=True,
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
        ResolvedToolBinding(
            tool_id="skill_installer",
            capability_aliases=("skill_installer", "skills.install"),
            requires_policy=False,
        ),
        ResolvedToolBinding(
            tool_id="request_user_input",
            capability_aliases=("request_user_input", "user_input", "conversation"),
            requires_policy=False,
        ),
        ResolvedToolBinding(
            tool_id="web_fetch",
            capability_aliases=("web_fetch", "web.fetch", "web"),
            requires_policy=True,
        ),
        ResolvedToolBinding(
            tool_id="web_search",
            capability_aliases=("web_search", "web.search", "web"),
            requires_policy=True,
        ),
        ResolvedToolBinding(
            tool_id="mcp_tools",
            capability_aliases=("mcp_tools", "mcp", "mcp.tools"),
            requires_policy=True,
        ),
    )


def _conversation_payload(request: "AgentExecutionRequest") -> list[dict[str, str]]:
    if request.conversation_messages:
        return [
            {"role": message["role"], "content": message["content"]}
            for message in request.conversation_messages
            if message.get("role") and message.get("content")
        ]
    return [{"role": "user", "content": request.objective.strip()}]


def _skill_payloads(skills: tuple[SkillDescriptor, ...]) -> list[str]:
    return [skill.prompt_text for skill in skills]


def _delegation_description(objective: str) -> str:
    return objective.strip()


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


def _extract_final_assistant_response(result: dict[str, Any]) -> str | None:
    messages = result.get("messages", [])
    for message in reversed(messages):
        role = getattr(message, "role", None)
        message_type = getattr(message, "type", None)
        content = getattr(message, "content", None)
        content_blocks = getattr(message, "content_blocks", None)
        if isinstance(message, dict):
            role = message.get("role", role)
            message_type = message.get("type", message_type)
            content = message.get("content", content)
            content_blocks = message.get("content_blocks", content_blocks)
        if role != "assistant" and message_type != "ai":
            continue
        normalized = _normalize_message_content(content_blocks)
        if normalized is None:
            normalized = _normalize_message_content(content)
        if normalized is not None:
            return normalized
    return None


def _write_final_response_artifact(
    *, request: "AgentExecutionRequest", final_response: str | None
) -> str | None:
    if final_response is None:
        return None
    sandbox_path = f"/workspace/artifacts/{request.task_id}/{request.run_id}/final_response.md"
    request.sandbox.write_text(sandbox_path, f"{final_response}\n")
    return request.sandbox.normalize_path(sandbox_path)


def _extract_error_message(result: dict[str, Any]) -> str | None:
    error = result.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    return None


def _normalize_message_content(content: Any) -> str | None:
    if isinstance(content, str):
        stripped = content.strip()
        return stripped or None
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for item in content:
        normalized = _normalize_content_block(item)
        if normalized is not None:
            parts.append(normalized)
    if not parts:
        return None
    return "\n".join(parts).strip() or None


def _normalize_content_block(block: Any) -> str | None:
    if isinstance(block, str):
        stripped = block.strip()
        return stripped or None
    if isinstance(block, dict):
        block_type = block.get("type")
        if block_type not in (None, "text", "output_text"):
            return None
        for key in ("text", "content", "value"):
            value = block.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    text = getattr(block, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    value = getattr(block, "content", None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _invoke_agent(
    agent: Any, payload: dict[str, Any], config: dict[str, Any] | None
) -> dict[str, Any]:
    if config is None:
        return agent.invoke(payload)
    try:
        return agent.invoke(payload, config=config)
    except TypeError:
        return agent.invoke(payload)


def _is_resumable_transient_execution_error(
    exc: Exception,
    request: "AgentExecutionRequest",
) -> bool:
    if request.checkpoint_controller is None:
        return False
    message = str(exc).lower()
    transient_markers = (
        "internal server error",
        "status code: -1",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
        "timed out",
        "timeout",
        "rate limit",
        "too many requests",
    )
    return any(marker in message for marker in transient_markers)


def _task_remote_mcp_state(
    state: ProviderRemoteMCPAuthorizationState,
) -> RemoteMCPAuthorizationState:
    return RemoteMCPAuthorizationState(
        server_name=state.server_name,
        provider_id=state.provider_id,
        status=state.status,
        summary=state.summary,
        actions=[
            RemoteMCPActionState(
                action_id=action.action_id,
                method=action.method,
                title=action.title,
                params=dict(action.params),
            )
            for action in state.actions
        ],
    )
