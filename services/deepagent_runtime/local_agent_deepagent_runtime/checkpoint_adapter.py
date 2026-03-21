from __future__ import annotations

import pickle
from dataclasses import dataclass
from typing import Any, Callable, Protocol, cast
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver

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
        self._checkpointers_by_thread: dict[str, Any | None] = {}

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

    def get_resume_handle(self, task_id: str, run_id: str) -> ResumeHandle | None:
        return self._checkpoint_store.get_resume_handle(task_id, run_id)

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
            checkpointer=self._checkpointer_for_thread(thread_id),
        )

    def _checkpointer_for_thread(self, thread_id: str) -> Any | None:
        if thread_id not in self._checkpointers_by_thread:
            self._checkpointers_by_thread[thread_id] = self._build_checkpointer(thread_id)
        return self._checkpointers_by_thread[thread_id]

    def _build_checkpointer(self, thread_id: str) -> Any | None:
        checkpointer = self._checkpointer_factory()
        if not isinstance(checkpointer, InMemorySaver):
            return checkpointer
        persistent = PersistentInMemorySaver(
            save_state=lambda state: self._checkpoint_store.save_thread_state(thread_id, state),
            serde=checkpointer.serde,
        )
        persisted_state = self._checkpoint_store.load_thread_state(thread_id)
        if persisted_state is not None:
            persistent.load_persisted_state(persisted_state)
        return persistent


class PersistentInMemorySaver(InMemorySaver):
    def __init__(
        self,
        *,
        save_state: Callable[[bytes], None],
        serde: Any | None = None,
    ) -> None:
        super().__init__(serde=serde)
        self._save_state = save_state

    def put(
        self,
        config: dict[str, Any],
        checkpoint: Any,
        metadata: Any,
        new_versions: Any,
    ) -> dict[str, Any]:
        result = super().put(config, checkpoint, metadata, new_versions)
        self._persist()
        return result

    def put_writes(
        self,
        config: dict[str, Any],
        writes: list[tuple[str, Any]] | tuple[tuple[str, Any], ...],
        task_id: str,
        task_path: str = "",
    ) -> None:
        super().put_writes(config, writes, task_id, task_path)
        self._persist()

    async def aput(
        self,
        config: dict[str, Any],
        checkpoint: Any,
        metadata: Any,
        new_versions: Any,
    ) -> dict[str, Any]:
        result = await super().aput(config, checkpoint, metadata, new_versions)
        self._persist()
        return result

    async def aput_writes(
        self,
        config: dict[str, Any],
        writes: list[tuple[str, Any]] | tuple[tuple[str, Any], ...],
        task_id: str,
        task_path: str = "",
    ) -> None:
        await super().aput_writes(config, writes, task_id, task_path)
        self._persist()

    def load_persisted_state(self, payload: bytes) -> None:
        state = cast(dict[str, Any], pickle.loads(payload))
        self.storage.clear()
        self.storage.update(_restore_storage(state.get("storage", {})))
        self.writes.clear()
        self.writes.update(_restore_writes(state.get("writes", {})))
        self.blobs.clear()
        self.blobs.update(_restore_blobs(state.get("blobs", {})))

    def _persist(self) -> None:
        self._save_state(
            pickle.dumps(
                {
                    "storage": _freeze_storage(self.storage),
                    "writes": _freeze_writes(self.writes),
                    "blobs": _freeze_blobs(self.blobs),
                },
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        )


def _freeze_storage(storage: Any) -> dict[str, dict[str, dict[str, tuple[Any, Any, Any]]]]:
    return {
        thread_id: {
            checkpoint_ns: dict(checkpoints)
            for checkpoint_ns, checkpoints in namespaces.items()
        }
        for thread_id, namespaces in storage.items()
    }


def _freeze_writes(writes: Any) -> dict[tuple[str, str, str], dict[tuple[str, int], tuple[Any, ...]]]:
    return {outer_key: dict(inner) for outer_key, inner in writes.items()}


def _freeze_blobs(blobs: Any) -> dict[tuple[str, str, str, Any], tuple[Any, bytes]]:
    return dict(blobs)


def _restore_storage(
    storage: dict[str, dict[str, dict[str, tuple[Any, Any, Any]]]],
) -> dict[str, Any]:
    restored: dict[str, Any] = {}
    for thread_id, namespaces in storage.items():
        restored[thread_id] = {
            checkpoint_ns: dict(checkpoints)
            for checkpoint_ns, checkpoints in namespaces.items()
        }
    return restored


def _restore_writes(
    writes: dict[tuple[str, str, str], dict[tuple[str, int], tuple[Any, ...]]],
) -> dict[tuple[str, str, str], dict[tuple[str, int], tuple[Any, ...]]]:
    return {outer_key: dict(inner) for outer_key, inner in writes.items()}


def _restore_blobs(
    blobs: dict[tuple[str, str, str, Any], tuple[Any, bytes]],
) -> dict[tuple[str, str, str, Any], tuple[Any, bytes]]:
    return dict(blobs)


def _default_checkpointer_factory() -> Any | None:
    try:  # pragma: no cover - exercised via integration paths
        from langgraph.checkpoint.memory import InMemorySaver
    except ImportError:  # pragma: no cover
        return None
    return InMemorySaver()
