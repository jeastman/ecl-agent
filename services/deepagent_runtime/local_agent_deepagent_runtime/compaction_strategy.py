from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from deepagents.backends import StateBackend
from deepagents.middleware.summarization import (
    SummarizationMiddleware,
    create_summarization_tool_middleware,
)
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.types import Command

from packages.config.local_agent_config.models import CompactionConfig
from packages.protocol.local_agent_protocol.models import utc_now_timestamp
from packages.task_model.local_agent_task_model.ids import new_event_id
from packages.task_model.local_agent_task_model.models import CompactionTrigger


@dataclass(slots=True)
class CompactionSnapshot:
    compaction_id: str
    trigger: CompactionTrigger
    strategy: str
    cutoff_index: int
    summary_content: str
    created_at: str
    provenance: dict[str, Any]
    artifact_path: str | None = None


@dataclass(slots=True)
class CompactionResult:
    snapshot: CompactionSnapshot | None
    projected_messages: list[dict[str, str]]


class CompactionStrategyPort(Protocol):
    strategy_id: str

    def build_middleware(
        self,
        *,
        model: Any,
        policy: CompactionConfig,
        on_compaction: Callable[[str, dict[str, Any]], None],
    ) -> list[AgentMiddleware]: ...

    def compact_messages(
        self,
        *,
        messages: list[dict[str, str]],
        trigger: CompactionTrigger,
    ) -> CompactionResult: ...


class _NullBackend:
    def download_files(self, paths: list[str]) -> list[Any]:
        return []

    def write(self, path: str, content: str) -> Any:  # pragma: no cover - not used explicitly
        return None

    def edit(self, path: str, old: str, new: str) -> Any:  # pragma: no cover - not used explicitly
        return None


class _CompactionObserverMiddleware(AgentMiddleware):
    def __init__(self, on_compaction: Callable[[str, dict[str, Any]], None]) -> None:
        self._on_compaction = on_compaction
        self._last_signature: tuple[Any, ...] | None = None

    def after_model(self, state: dict[str, Any], runtime: Any) -> dict[str, Any] | None:
        event = state.get("_summarization_event")
        self._emit_if_new(event, CompactionTrigger.THRESHOLD)
        return None

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        result = handler(request)
        if request.tool_call.get("name") != "compact_conversation":
            return result
        update = getattr(result, "update", None)
        if not isinstance(update, dict):
            return result
        event = update.get("_summarization_event")
        self._emit_if_new(event, CompactionTrigger.EXPLICIT_AGENT)
        return result

    def _emit_if_new(self, event: Any, trigger: CompactionTrigger) -> None:
        if not isinstance(event, dict):
            return
        summary_message = event.get("summary_message")
        cutoff_index = event.get("cutoff_index")
        file_path = event.get("file_path")
        summary_content = getattr(summary_message, "content", None)
        signature = (cutoff_index, file_path, summary_content)
        if signature == self._last_signature:
            return
        self._last_signature = signature
        if not isinstance(cutoff_index, int):
            return
        self._on_compaction(
            "conversation.compacted",
            {
                "compaction_id": new_event_id(),
                "trigger": trigger.value,
                "strategy": "deepagents_native",
                "cutoff_index": cutoff_index,
                "summary": "Conversation context compacted during Deep Agent execution.",
                "created_at": utc_now_timestamp(),
                "artifact_path": file_path if isinstance(file_path, str) else None,
            },
        )


class DeepAgentsNativeCompactionStrategy:
    strategy_id = "deepagents_native"

    def __init__(
        self,
        *,
        model_name: str,
        model_provider: str,
        model_factory: Callable[[str], Any] | Callable[..., Any],
        policy: CompactionConfig | None = None,
    ) -> None:
        self._model_name = model_name
        self._model_provider = model_provider
        self._model_factory = model_factory
        self._policy = policy or CompactionConfig()

    def build_middleware(
        self,
        *,
        model: Any,
        policy: CompactionConfig,
        on_compaction: Callable[[str, dict[str, Any]], None],
    ) -> list[AgentMiddleware]:
        middleware: list[AgentMiddleware] = [_CompactionObserverMiddleware(on_compaction)]
        if policy.explicit_agent_tool:
            middleware.append(create_summarization_tool_middleware(model, StateBackend))
        return middleware

    def compact_messages(
        self,
        *,
        messages: list[dict[str, str]],
        trigger: CompactionTrigger,
    ) -> CompactionResult:
        if len(messages) <= 1:
            return CompactionResult(snapshot=None, projected_messages=list(messages))
        model = self._model_factory(self._model_name, model_provider=self._model_provider)
        middleware = SummarizationMiddleware(
            model=model,
            backend=_NullBackend(),
            trigger=(self._policy.trigger.kind, self._policy.trigger.value),
            keep=(self._policy.keep.kind, self._policy.keep.value),
            trim_tokens_to_summarize=None,
        )
        base_messages = [_message_from_payload(message) for message in messages]
        cutoff_index = middleware._determine_cutoff_index(base_messages)
        if cutoff_index <= 0:
            return CompactionResult(snapshot=None, projected_messages=list(messages))
        to_summarize, preserved = middleware._partition_messages(base_messages, cutoff_index)
        summary = middleware._create_summary(to_summarize)
        summary_message = middleware._build_new_messages_with_path(summary, None)[0]
        snapshot = CompactionSnapshot(
            compaction_id=f"cmp_{new_event_id()}",
            trigger=trigger,
            strategy=self.strategy_id,
            cutoff_index=cutoff_index,
            summary_content=str(summary_message.content),
            created_at=utc_now_timestamp(),
            provenance={"message_count": len(messages)},
            artifact_path=None,
        )
        projected_messages = [
            {"role": "user", "content": str(summary_message.content)},
            *[_payload_from_message(message) for message in preserved],
        ]
        return CompactionResult(snapshot=snapshot, projected_messages=projected_messages)


def _message_from_payload(payload: dict[str, str]) -> BaseMessage:
    role = payload.get("role", "")
    content = payload.get("content", "")
    if role == "assistant":
        return AIMessage(content=content)
    if role == "system":
        return SystemMessage(content=content)
    return HumanMessage(content=content)


def _payload_from_message(message: BaseMessage) -> dict[str, str]:
    role = "user"
    if isinstance(message, AIMessage):
        role = "assistant"
    elif isinstance(message, SystemMessage):
        role = "system"
    return {"role": role, "content": str(message.content)}
