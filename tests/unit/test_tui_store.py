from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.store.app_state import AppStateStore
from apps.tui.local_agent_tui.store.selectors import (
    approval_count,
    artifact_count,
    pending_approvals,
    recent_artifacts,
    selected_task_summary,
    task_count,
)


class TuiStoreTests(unittest.TestCase):
    def test_runtime_health_and_connection_state_flow(self) -> None:
        store = AppStateStore()
        store.dispatch({"kind": "connection", "status": "connecting"})
        store.dispatch(
            {
                "kind": "rpc",
                "name": "runtime.health",
                "payload": {"result": {"status": "ok", "protocol_version": "1.0.0"}},
            }
        )
        state = store.snapshot()
        self.assertEqual(state.connection_status, "connected")
        self.assertEqual(state.runtime_health["status"], "ok")

    def test_runtime_events_project_task_approval_and_artifact_counts(self) -> None:
        store = AppStateStore()
        store.dispatch(
            {
                "kind": "event",
                "payload": {
                    "event": {
                        "event_type": "task.created",
                        "timestamp": "2026-03-12T00:00:00Z",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "payload": {"status": "created", "objective": "Inspect repo"},
                    }
                },
            }
        )
        store.dispatch(
            {
                "kind": "event",
                "payload": {
                    "event": {
                        "event_type": "approval.requested",
                        "timestamp": "2026-03-12T00:00:01Z",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "payload": {
                            "approval": {
                                "approval_id": "approval_1",
                                "task_id": "task_1",
                                "run_id": "run_1",
                                "status": "pending",
                            }
                        },
                    }
                },
            }
        )
        store.dispatch(
            {
                "kind": "event",
                "payload": {
                    "event": {
                        "event_type": "artifact.created",
                        "timestamp": "2026-03-12T00:00:02Z",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "payload": {
                            "artifact": {
                                "artifact_id": "artifact_1",
                                "task_id": "task_1",
                                "run_id": "run_1",
                            }
                        },
                    }
                },
            }
        )
        state = store.snapshot()
        self.assertEqual(task_count(state), 1)
        self.assertEqual(approval_count(state), 1)
        self.assertEqual(artifact_count(state), 1)

    def test_task_get_and_list_results_populate_cached_state(self) -> None:
        store = AppStateStore()
        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.list",
                "payload": {
                    "result": {
                        "tasks": [
                            {
                                "task_id": "task_1",
                                "run_id": "run_1",
                                "status": "executing",
                                "objective": "Inspect repo",
                                "updated_at": "2026-03-12T00:00:00Z",
                            },
                            {
                                "task_id": "task_2",
                                "run_id": "run_2",
                                "status": "paused",
                                "objective": "Review docs",
                                "updated_at": "2026-03-11T00:00:00Z",
                            },
                        ]
                    }
                },
            }
        )
        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.get",
                "payload": {
                    "result": {
                        "task": {
                            "task_id": "task_1",
                            "run_id": "run_1",
                            "status": "executing",
                            "objective": "Inspect repo",
                        }
                    }
                },
            }
        )
        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.approvals.list",
                "payload": {
                    "result": {
                        "approvals": [
                            {
                                "approval_id": "approval_1",
                                "task_id": "task_1",
                                "run_id": "run_1",
                                "status": "pending",
                            }
                        ]
                    }
                },
            }
        )
        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.artifacts.list",
                "payload": {
                    "result": {
                        "artifacts": [
                            {
                                "artifact_id": "artifact_1",
                                "task_id": "task_1",
                                "run_id": "run_1",
                            }
                        ]
                    }
                },
            }
        )
        state = store.snapshot()
        self.assertEqual(task_count(state), 2)
        self.assertEqual(approval_count(state), 1)
        self.assertEqual(artifact_count(state), 1)
        self.assertEqual(selected_task_summary(state).task_id, "task_1")  # type: ignore[union-attr]
        self.assertEqual(pending_approvals(state)[0].approval_id, "approval_1")
        self.assertEqual(recent_artifacts(state)[0].artifact_id, "artifact_1")

    def test_selected_task_survives_updates_for_other_tasks(self) -> None:
        store = AppStateStore()
        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.list",
                "payload": {
                    "result": {
                        "tasks": [
                            {
                                "task_id": "task_1",
                                "run_id": "run_1",
                                "status": "executing",
                                "objective": "Inspect repo",
                                "updated_at": "2026-03-12T00:00:00Z",
                            },
                            {
                                "task_id": "task_2",
                                "run_id": "run_2",
                                "status": "paused",
                                "objective": "Review docs",
                                "updated_at": "2026-03-11T00:00:00Z",
                            },
                        ]
                    }
                },
            }
        )
        store.dispatch({"kind": "ui", "selected_task_id": "task_2"})
        store.dispatch(
            {
                "kind": "event",
                "payload": {
                    "event": {
                        "event_type": "artifact.created",
                        "timestamp": "2026-03-12T00:00:02Z",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "payload": {
                            "artifact": {
                                "artifact_id": "artifact_1",
                                "task_id": "task_1",
                                "run_id": "run_1",
                            }
                        },
                    }
                },
            }
        )
        self.assertEqual(store.snapshot().selected_task_id, "task_2")
