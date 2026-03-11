from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol
from uuid import uuid4

from packages.protocol.local_agent_protocol.models import utc_now_timestamp
from services.checkpoint_service.local_agent_checkpoint_service.checkpoint_models import (
    CheckpointMetadata,
    ResumeHandle,
)
from services.checkpoint_service.local_agent_checkpoint_service.checkpoint_store import (
    CheckpointStore,
)


class CheckpointController(Protocol):
    @property
    def thread_id(self) -> str: ...

    @property
    def latest_checkpoint_id(self) -> str | None: ...

    @property
    def is_resumed(self) -> bool: ...

    def build_agent_kwargs(self) -> dict[str, Any]: ...

    def build_invoke_config(self) -> dict[str, Any]: ...

    def record_checkpoint(self, reason: str | None = None) -> CheckpointMetadata: ...


@dataclass(slots=True)
class LangGraphCheckpointController:
    checkpoint_store: CheckpointStore
    task_id: str
    run_id: str
    thread_id: str
    latest_checkpoint_id: str | None = None
    next_checkpoint_index: int = 0
    is_resumed: bool = False
    checkpointer: Any | None = None

    def build_agent_kwargs(self) -> dict[str, Any]:
        if self.checkpointer is None:
            return {}
        return {"checkpointer": self.checkpointer}

    def build_invoke_config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id}}

    def record_checkpoint(self, reason: str | None = None) -> CheckpointMetadata:
        metadata = CheckpointMetadata(
            checkpoint_id=f"ckpt_{uuid4().hex}",
            task_id=self.task_id,
            run_id=self.run_id,
            thread_id=self.thread_id,
            checkpoint_index=self.next_checkpoint_index,
            created_at=utc_now_timestamp(),
            reason=reason,
        )
        self.checkpoint_store.save_metadata(metadata)
        self.latest_checkpoint_id = metadata.checkpoint_id
        self.next_checkpoint_index += 1
        return metadata


class LangGraphCheckpointAdapter:
    def __init__(
        self,
        checkpoint_store: CheckpointStore,
        *,
        checkpointer_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._checkpoint_store = checkpoint_store
        self._checkpointer_factory = checkpointer_factory or _default_checkpointer_factory

    def begin_run(self, task_id: str, run_id: str) -> LangGraphCheckpointController:
        thread_id = self._checkpoint_store.create_thread(task_id, run_id)
        return self.attach_thread(task_id, run_id, thread_id)

    def attach_thread(
        self,
        task_id: str,
        run_id: str,
        thread_id: str,
    ) -> LangGraphCheckpointController:
        return self._build_controller(
            task_id=task_id,
            run_id=run_id,
            thread_id=thread_id,
            latest_checkpoint_id=None,
            is_resumed=False,
        )

    def resume_run(self, task_id: str, run_id: str) -> LangGraphCheckpointController:
        handle = self._checkpoint_store.get_resume_handle(task_id, run_id)
        if handle is None:
            raise ValueError(f"no resume handle for {task_id}/{run_id}")
        return self._build_from_handle(handle)

    def restore_from_handle(self, handle: ResumeHandle) -> LangGraphCheckpointController:
        return self._build_from_handle(handle)

    def _build_from_handle(self, handle: ResumeHandle) -> LangGraphCheckpointController:
        return self._build_controller(
            task_id=handle.task_id,
            run_id=handle.run_id,
            thread_id=handle.thread_id,
            latest_checkpoint_id=handle.latest_checkpoint_id,
            is_resumed=True,
        )

    def _build_controller(
        self,
        *,
        task_id: str,
        run_id: str,
        thread_id: str,
        latest_checkpoint_id: str | None,
        is_resumed: bool,
    ) -> LangGraphCheckpointController:
        checkpoints = self._checkpoint_store.list_checkpoints(task_id, run_id)
        return LangGraphCheckpointController(
            checkpoint_store=self._checkpoint_store,
            task_id=task_id,
            run_id=run_id,
            thread_id=thread_id,
            latest_checkpoint_id=latest_checkpoint_id,
            next_checkpoint_index=len(checkpoints),
            is_resumed=is_resumed,
            checkpointer=self._checkpointer_factory(),
        )


def _default_checkpointer_factory() -> Any | None:
    try:  # pragma: no cover - exercised via integration paths
        from langgraph.checkpoint.memory import InMemorySaver
    except ImportError:  # pragma: no cover
        return None
    return InMemorySaver()
