from __future__ import annotations

import unittest

from apps.runtime.local_agent_runtime.run_state_store import InMemoryRunStateStore
from packages.task_model.local_agent_task_model.models import RunState, TaskStatus


class RunStateStoreTests(unittest.TestCase):
    def test_create_get_and_update_state(self) -> None:
        store = InMemoryRunStateStore()
        state = RunState(
            task_id="task_1",
            run_id="run_1",
            status=TaskStatus.ACCEPTED,
            objective="Inspect the repo",
            created_at="2026-03-10T00:00:00Z",
            updated_at="2026-03-10T00:00:00Z",
            accepted_at="2026-03-10T00:00:00Z",
            workspace_roots=["."],
        )
        store.create(state)
        updated = store.update(
            "task_1",
            "run_1",
            status=TaskStatus.COMPLETED,
            current_phase="completed",
            active_subagent="primary",
            last_event_at="2026-03-10T00:01:00Z",
        )
        self.assertEqual(updated.status, TaskStatus.COMPLETED)
        self.assertEqual(store.get("task_1", "run_1").current_phase, "completed")
        self.assertEqual(store.get("task_1", "run_1").active_subagent, "primary")

    def test_missing_task_raises(self) -> None:
        store = InMemoryRunStateStore()
        with self.assertRaisesRegex(KeyError, "unknown task"):
            store.get("task_missing")


if __name__ == "__main__":
    unittest.main()
