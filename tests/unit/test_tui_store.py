from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.store.app_state import AppStateStore
from apps.tui.local_agent_tui.store.selectors import (
    approval_count,
    artifact_count,
    pending_approvals,
    recent_artifacts,
    selected_approval_detail,
    selected_task_header,
    selected_task_summary,
    task_action_bar,
    task_count,
    task_notifications,
    task_plan_view,
    task_subagent_activity,
    task_timeline,
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
        self._dispatch_created(store)
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

    def test_selected_approval_detail_projects_metadata(self) -> None:
        store = AppStateStore()
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
                                "type": "boundary",
                                "scope": {
                                    "boundary_key": "sandbox",
                                    "path_scope": "/workspace/docs/spec.md",
                                },
                                "scope_summary": "filesystem.write",
                                "description": "Write a generated spec",
                                "created_at": "2026-03-12T00:00:01Z",
                            }
                        ]
                    }
                },
            }
        )
        state = store.snapshot()
        detail = selected_approval_detail(state)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail.request_type, "boundary")
        self.assertEqual(detail.policy_context, "sandbox")
        self.assertEqual(detail.requested_action, "/workspace/docs/spec.md")

    def test_approval_refresh_falls_back_to_next_pending_selection(self) -> None:
        store = AppStateStore()
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
                                "created_at": "2026-03-12T00:00:02Z",
                            }
                        ]
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
                                "approval_id": "approval_2",
                                "task_id": "task_2",
                                "run_id": "run_2",
                                "status": "pending",
                                "created_at": "2026-03-12T00:00:03Z",
                            }
                        ]
                    }
                },
            }
        )
        self.assertEqual(store.snapshot().selected_approval_id, "approval_1")
        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.approve",
                "payload": {
                    "result": {
                        "approval_id": "approval_1",
                        "accepted": True,
                        "status": "approved",
                        "task": {
                            "task_id": "task_1",
                            "run_id": "run_1",
                            "status": "executing",
                            "objective": "Inspect repo",
                            "updated_at": "2026-03-12T00:00:04Z",
                        },
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
                                "status": "approved",
                                "created_at": "2026-03-12T00:00:02Z",
                            }
                        ]
                    }
                },
            }
        )
        self.assertEqual(store.snapshot().selected_approval_id, "approval_2")

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

    def test_task_detail_selectors_project_timeline_plan_subagents_and_actions(self) -> None:
        store = AppStateStore()
        self._dispatch_created(store)
        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.logs.stream",
                "payload": {"result": {"task_id": "task_1", "run_id": "run_1"}},
            }
        )
        store.dispatch(
            {
                "kind": "event",
                "payload": {
                    "event": {
                        "event_type": "plan.updated",
                        "timestamp": "2026-03-12T00:00:01Z",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "payload": {"summary": "Analyze repository", "phase": "planning"},
                    }
                },
            }
        )
        store.dispatch(
            {
                "kind": "event",
                "payload": {
                    "event": {
                        "event_type": "tool.called",
                        "timestamp": "2026-03-12T00:00:02Z",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "payload": {"tool": "filesystem.read"},
                    }
                },
            }
        )
        store.dispatch(
            {
                "kind": "event",
                "payload": {
                    "event": {
                        "event_type": "tool.called",
                        "timestamp": "2026-03-12T00:00:03Z",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "payload": {"tool": "filesystem.read"},
                    }
                },
            }
        )
        store.dispatch(
            {
                "kind": "event",
                "payload": {
                    "event": {
                        "event_type": "subagent.started",
                        "timestamp": "2026-03-12T00:00:04Z",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "payload": {
                            "subagentId": "researcher",
                            "taskDescription": "Inspect docs",
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
                        "timestamp": "2026-03-12T00:00:05Z",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "payload": {
                            "artifact": {
                                "artifact_id": "artifact_1",
                                "task_id": "task_1",
                                "run_id": "run_1",
                                "display_name": "report.md",
                                "logical_path": "/artifacts/report.md",
                                "created_at": "2026-03-12T00:00:05Z",
                            }
                        },
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
                            "status": "paused",
                            "objective": "Inspect repo",
                            "created_at": "2026-03-12T00:00:00Z",
                            "updated_at": "2026-03-12T00:00:05Z",
                            "is_resumable": True,
                            "links": {"resume": "task.resume"},
                        }
                    }
                },
            }
        )

        state = store.snapshot()
        header = selected_task_header(state)
        timeline = task_timeline(state)
        plan = task_plan_view(state)
        subagents = task_subagent_activity(state)
        actions = task_action_bar(state)
        notifications = task_notifications(state)

        self.assertEqual(header.current_phase, "planning")  # type: ignore[union-attr]
        self.assertEqual(plan.current_step, "Analyze repository")
        self.assertEqual(timeline.events[2].repeat_count, 2)
        self.assertEqual(subagents[0].subagent_id, "researcher")
        self.assertEqual(subagents[0].status, "RUNNING")
        self.assertTrue(actions.resume_enabled)
        self.assertTrue(actions.artifact_open_enabled)
        self.assertEqual(notifications.items[-1].summary, "report.md")

    def test_event_buffers_are_capped_and_deduplicate_artifacts_and_approvals(self) -> None:
        store = AppStateStore()
        self._dispatch_created(store)
        for index in range(260):
            store.dispatch(
                {
                    "kind": "event",
                    "payload": {
                        "event": {
                            "event_type": "tool.called",
                            "timestamp": f"2026-03-12T00:00:{index:02d}Z",
                            "task_id": "task_1",
                            "run_id": "run_1",
                            "payload": {"tool": f"tool_{index}"},
                        }
                    },
                }
            )
        duplicate_artifact = {
            "artifact_id": "artifact_1",
            "task_id": "task_1",
            "run_id": "run_1",
        }
        duplicate_approval = {
            "approval_id": "approval_1",
            "task_id": "task_1",
            "run_id": "run_1",
            "status": "pending",
        }
        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.artifacts.list",
                "payload": {"result": {"artifacts": [duplicate_artifact, duplicate_artifact]}},
            }
        )
        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.approvals.list",
                "payload": {"result": {"approvals": [duplicate_approval, duplicate_approval]}},
            }
        )
        state = store.snapshot()
        self.assertEqual(len(state.run_event_buffers[("task_1", "run_1")]), 250)
        self.assertEqual(len(state.artifacts_by_task[("task_1", "run_1")]), 1)
        self.assertEqual(len(state.approvals_by_task[("task_1", "run_1")]), 1)

    @staticmethod
    def _dispatch_created(store: AppStateStore) -> None:
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
