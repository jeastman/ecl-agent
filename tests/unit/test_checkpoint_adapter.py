from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from langgraph.checkpoint.memory import InMemorySaver

from services.checkpoint_service.local_agent_checkpoint_service.checkpoint_store import (
    SQLiteCheckpointStore,
)
from services.checkpoint_service.local_agent_checkpoint_service.thread_registry import (
    SQLiteThreadRegistry,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.checkpoint_adapter import (
    LangGraphCheckpointAdapter,
    PersistentInMemorySaver,
)


class CheckpointAdapterTests(unittest.TestCase):
    def test_resume_run_reuses_existing_thread_checkpointer(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            database_path = str(Path(temp_dir) / "runtime.db")
            registry = SQLiteThreadRegistry(database_path)
            store = SQLiteCheckpointStore(database_path, thread_registry=registry)
            created_checkpointers: list[object] = []

            def build_checkpointer() -> object:
                checkpointer = object()
                created_checkpointers.append(checkpointer)
                return checkpointer

            adapter = LangGraphCheckpointAdapter(
                store,
                checkpointer_factory=build_checkpointer,
            )

            started = adapter.begin_run("task_1", "run_1")
            started.record_checkpoint("run_started")
            resumed = adapter.resume_run("task_1", "run_1")

            self.assertIs(resumed.checkpointer, started.checkpointer)
            self.assertEqual(created_checkpointers, [started.checkpointer])

    def test_resume_run_rehydrates_persisted_in_memory_saver_after_restart(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            database_path = str(Path(temp_dir) / "runtime.db")
            registry = SQLiteThreadRegistry(database_path)
            store = SQLiteCheckpointStore(database_path, thread_registry=registry)

            adapter = LangGraphCheckpointAdapter(store, checkpointer_factory=InMemorySaver)
            started = adapter.begin_run("task_1", "run_1")
            assert isinstance(started.checkpointer, InMemorySaver)
            started.checkpointer.put(
                {"configurable": {"thread_id": started.thread_id, "checkpoint_ns": ""}},
                {
                    "id": "ckpt_graph_1",
                    "ts": "2026-03-20T00:00:00Z",
                    "channel_values": {"messages": ["hello"]},
                    "channel_versions": {"messages": "1"},
                    "versions_seen": {},
                    "pending_sends": [],
                },
                {},
                {"messages": "1"},
            )
            started.record_checkpoint("awaiting_approval")

            restarted = LangGraphCheckpointAdapter(store, checkpointer_factory=InMemorySaver)
            resumed = restarted.resume_run("task_1", "run_1")
            assert isinstance(resumed.checkpointer, InMemorySaver)

            restored = resumed.checkpointer.get_tuple(
                {"configurable": {"thread_id": resumed.thread_id, "checkpoint_ns": ""}}
            )
            assert restored is not None
            self.assertEqual(restored.checkpoint["channel_values"]["messages"], ["hello"])

    def test_persistent_in_memory_saver_serializes_concurrent_put_writes_during_persist(self) -> None:
        saver = PersistentInMemorySaver(save_state=lambda _: None)
        config_a = {
            "configurable": {
                "thread_id": "thread_1",
                "checkpoint_ns": "",
                "checkpoint_id": "ckpt_a",
            }
        }
        config_b = {
            "configurable": {
                "thread_id": "thread_1",
                "checkpoint_ns": "",
                "checkpoint_id": "ckpt_b",
            }
        }
        config_c = {
            "configurable": {
                "thread_id": "thread_1",
                "checkpoint_ns": "",
                "checkpoint_id": "ckpt_c",
            }
        }
        saver.put_writes(config_a, [("messages", "a")], "task_a")
        saver.put_writes(config_b, [("messages", "b")], "task_b")

        original_freeze_writes = (
            "services.deepagent_runtime.local_agent_deepagent_runtime.checkpoint_adapter._freeze_writes"
        )
        started = threading.Event()
        mutation_finished = threading.Event()
        failure: list[BaseException] = []

        def controlled_freeze_writes(writes: object) -> dict[object, dict[object, tuple[object, ...]]]:
            iterator = iter(cast(dict[object, dict[object, tuple[object, ...]]], writes).items())
            first_key, first_value = next(iterator)
            started.set()
            time.sleep(0.05)
            frozen = {first_key: dict(first_value)}
            for outer_key, inner in iterator:
                frozen[outer_key] = dict(inner)
            return frozen

        def mutate_writes() -> None:
            started.wait(timeout=1.0)
            try:
                saver.put_writes(config_c, [("messages", "c")], "task_c")
            except BaseException as exc:  # pragma: no cover - surfaced by assertion below
                failure.append(exc)
            finally:
                mutation_finished.set()

        worker = threading.Thread(target=mutate_writes)
        worker.start()
        try:
            with patch(original_freeze_writes, controlled_freeze_writes):
                saver._persist()
        finally:
            worker.join(timeout=1.0)

        self.assertFalse(failure, failure)
        self.assertTrue(mutation_finished.is_set())
