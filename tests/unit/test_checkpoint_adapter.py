from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from services.checkpoint_service.local_agent_checkpoint_service.checkpoint_store import (
    SQLiteCheckpointStore,
)
from services.checkpoint_service.local_agent_checkpoint_service.thread_registry import (
    SQLiteThreadRegistry,
)
from services.deepagent_runtime.local_agent_deepagent_runtime.checkpoint_adapter import (
    LangGraphCheckpointAdapter,
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
