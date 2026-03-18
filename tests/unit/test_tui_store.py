from __future__ import annotations

import unittest

from apps.tui.local_agent_tui.store.app_state import AppStateStore
from apps.tui.local_agent_tui.store.selectors import (
    approval_count,
    artifact_browser_rows,
    config_section_items,
    connection_label,
    diagnostics_count,
    diagnostics_items,
    footer_hints,
    selected_artifact_preview,
    selected_config_detail,
    selected_diagnostics_detail,
    selected_markdown_artifact,
    artifact_count,
    memory_entry_items,
    memory_group_summary,
    memory_scope_groups,
    pending_approvals,
    pending_approvals_for_selected_task,
    recent_artifacts,
    selected_approval_detail,
    selected_memory_detail,
    selected_task_header,
    selected_task_summary,
    task_action_bar,
    task_count,
    task_notifications,
    task_plan_view,
    task_subagent_activity,
    task_timeline,
    command_palette,
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

    def test_connection_label_hides_last_error_when_runtime_is_connected(self) -> None:
        store = AppStateStore()
        store.dispatch(
            {
                "kind": "connection",
                "status": "connected",
                "error": "{'code': -32602, 'message': 'sandbox path must be under /workspace'}",
            }
        )
        self.assertEqual(connection_label(store.snapshot()), "connected")

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

    def test_selected_task_switch_updates_pending_approval_selection(self) -> None:
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
                "name": "task.approvals.list",
                "payload": {
                    "result": {
                        "approvals": [
                            {
                                "approval_id": "approval_1",
                                "task_id": "task_1",
                                "run_id": "run_1",
                                "status": "pending",
                                "created_at": "2026-03-12T00:00:01Z",
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
                                "created_at": "2026-03-12T00:00:02Z",
                            }
                        ]
                    }
                },
            }
        )

        store.dispatch({"kind": "ui", "selected_task_id": "task_2"})
        state = store.snapshot()
        self.assertEqual(state.selected_approval_id, "approval_2")
        self.assertEqual(
            [approval.approval_id for approval in pending_approvals_for_selected_task(state)],
            ["approval_2"],
        )

        store.dispatch({"kind": "ui", "selected_task_id": "task_1"})
        state = store.snapshot()
        self.assertEqual(state.selected_approval_id, "approval_1")
        self.assertEqual(
            [approval.approval_id for approval in pending_approvals_for_selected_task(state)],
            ["approval_1"],
        )

    def test_command_palette_filters_available_commands(self) -> None:
        store = AppStateStore()
        self._dispatch_created(store)
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
                "kind": "ui",
                "command_palette_query": "approve",
            }
        )
        items = command_palette(store.snapshot()).items
        self.assertEqual([item.command_id for item in items], ["approve_request"])

    def test_task_timeline_respects_filter_and_search_state(self) -> None:
        store = AppStateStore()
        self._dispatch_created(store)
        store.dispatch(
            {
                "kind": "event",
                "payload": {
                    "event": {
                        "event_type": "tool.called",
                        "timestamp": "2026-03-12T00:00:01Z",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "payload": {"tool": "shell", "path": "/tmp/out.txt"},
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
                        "timestamp": "2026-03-12T00:00:02Z",
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
        store.dispatch({"kind": "ui", "task_timeline_filter": "tools"})
        timeline = task_timeline(store.snapshot())
        self.assertEqual([event.event_type for event in timeline.events], ["tool.called"])
        store.dispatch(
            {
                "kind": "ui",
                "task_timeline_filter": "all",
                "task_timeline_search_query": "approval",
            }
        )
        searched = task_timeline(store.snapshot())
        self.assertEqual([event.event_type for event in searched.events], ["approval.requested"])

    def test_diagnostics_rpc_and_detail_projection(self) -> None:
        store = AppStateStore()
        self._dispatch_created(store)
        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.diagnostics.list",
                "payload": {
                    "context": {"task_id": "task_1", "run_id": "run_1"},
                    "result": {
                        "diagnostics": [
                            {
                                "diagnostic_id": "diag_1",
                                "task_id": "task_1",
                                "run_id": "run_1",
                                "kind": "runtime_error",
                                "message": "Task failed to continue.",
                                "created_at": "2026-03-12T00:00:05Z",
                                "details": {"code": "boom"},
                            }
                        ]
                    },
                },
            }
        )
        state = store.snapshot()
        self.assertEqual(diagnostics_count(state), 1)
        self.assertEqual(diagnostics_items(state)[0].diagnostic_id, "diag_1")
        self.assertIn("boom", selected_diagnostics_detail(state).body)

    def test_timeline_collapse_keeps_latest_timestamp_for_repeated_tool_calls(self) -> None:
        store = AppStateStore()
        self._dispatch_created(store)
        for second in ("01", "02"):
            store.dispatch(
                {
                    "kind": "event",
                    "payload": {
                        "event": {
                            "event_type": "tool.called",
                            "timestamp": f"2026-03-12T00:00:{second}Z",
                            "task_id": "task_1",
                            "run_id": "run_1",
                            "payload": {"tool": "filesystem.read", "path": "/tmp/report.md"},
                            "source": {"name": "worker"},
                        }
                    },
                }
            )
        collapsed = task_timeline(store.snapshot()).events
        self.assertEqual(collapsed[-1].repeat_count, 2)
        self.assertEqual(collapsed[-1].timestamp, "2026-03-12T00:00:02Z")

    def test_footer_hints_include_palette_and_new_task(self) -> None:
        store = AppStateStore()
        hints = footer_hints(store.snapshot())
        self.assertIn("G Palette", hints)
        self.assertIn("N New Task", hints)

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
                                "logical_path": "/workspace/artifacts/report.md",
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
        self.assertEqual(plan.current_step, "Inspect docs")
        self.assertEqual(timeline.events[2].repeat_count, 2)
        self.assertEqual(subagents[0].subagent_id, "researcher")
        self.assertEqual(subagents[0].status, "RUNNING")
        self.assertTrue(actions.resume_enabled)
        self.assertTrue(actions.artifact_open_enabled)
        self.assertEqual(notifications.items[-1].summary, "report.md")

    def test_task_plan_view_tracks_live_subagent_summary(self) -> None:
        store = AppStateStore()
        self._dispatch_created(store)
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
                        "event_type": "subagent.started",
                        "timestamp": "2026-03-12T00:00:02Z",
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

        plan = task_plan_view(store.snapshot())

        self.assertEqual(plan.current_phase, "planning")
        self.assertEqual(plan.current_step, "Inspect docs")
        self.assertEqual(plan.recent_updates[-1].summary, "Analyze repository")

    def test_task_subagent_activity_falls_back_to_active_snapshot(self) -> None:
        store = AppStateStore()
        self._dispatch_created(store)
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
                            "created_at": "2026-03-12T00:00:00Z",
                            "updated_at": "2026-03-12T00:00:02Z",
                            "current_phase": "executing",
                            "latest_summary": "Inspect docs",
                            "active_subagent": "researcher",
                        }
                    }
                },
            }
        )

        subagents = task_subagent_activity(store.snapshot())

        self.assertEqual(len(subagents), 1)
        self.assertEqual(subagents[0].subagent_id, "researcher")
        self.assertEqual(subagents[0].status, "RUNNING")
        self.assertEqual(subagents[0].latest_summary, "Inspect docs")

    def test_tool_called_execute_command_summary_shows_command_and_cwd(self) -> None:
        store = AppStateStore()
        self._dispatch_created(store)
        store.dispatch(
            {
                "kind": "event",
                "payload": {
                    "event": {
                        "event_type": "tool.called",
                        "timestamp": "2026-03-12T00:00:02Z",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "payload": {
                            "tool": "execute_command",
                            "command": ["rm", "-f", "/tmp/ecl/cache file.txt"],
                            "cwd": "/tmp/ecl",
                        },
                    }
                },
            }
        )

        timeline = task_timeline(store.snapshot())

        self.assertEqual(timeline.events[-1].summary, "rm -f '/tmp/ecl/cache file.txt' (/tmp/ecl)")

    def test_task_logs_stream_does_not_change_selected_task(self) -> None:
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
                "kind": "rpc",
                "name": "task.logs.stream",
                "payload": {"result": {"task_id": "task_1", "run_id": "run_1"}},
            }
        )
        self.assertEqual(store.snapshot().selected_task_id, "task_2")

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

    def test_artifact_browser_selectors_project_grouping_and_preview(self) -> None:
        store = AppStateStore()
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
                                "display_name": "report.md",
                                "logical_path": "/workspace/artifacts/report.md",
                                "content_type": "text/markdown",
                                "created_at": "2026-03-12T00:00:05Z",
                            },
                            {
                                "artifact_id": "artifact_2",
                                "task_id": "task_1",
                                "run_id": "run_2",
                                "display_name": "trace.json",
                                "logical_path": "/workspace/artifacts/trace.json",
                                "content_type": "application/json",
                                "created_at": "2026-03-12T00:00:04Z",
                            },
                        ]
                    }
                },
            }
        )
        store.dispatch({"kind": "ui", "artifact_browser_selected_id": "artifact_1"})
        store.dispatch(
            {
                "kind": "ui",
                "artifact_preview_artifact_id": "artifact_1",
                "artifact_preview_status": "loading",
            }
        )
        loading_preview = selected_artifact_preview(store.snapshot())
        self.assertEqual(loading_preview.status, "loading")

        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.artifact.get",
                "payload": {
                    "result": {
                        "artifact": {
                            "artifact_id": "artifact_1",
                            "task_id": "task_1",
                            "run_id": "run_1",
                            "display_name": "report.md",
                            "logical_path": "/workspace/artifacts/report.md",
                            "content_type": "text/markdown",
                            "created_at": "2026-03-12T00:00:05Z",
                        },
                        "preview": {
                            "kind": "markdown",
                            "text": "# Report\n",
                            "encoding": "utf-8",
                        },
                        "external_open_supported": False,
                    }
                },
            }
        )
        store.dispatch({"kind": "ui", "markdown_viewer_artifact_id": "artifact_1"})
        state = store.snapshot()
        rows = artifact_browser_rows(state)
        preview = selected_artifact_preview(state)
        markdown = selected_markdown_artifact(state)
        self.assertEqual(rows[0].group_label, "task_1")
        self.assertEqual(preview.status, "loaded")
        self.assertIn("# Report", preview.body)
        self.assertEqual(markdown.display_name, "report.md")  # type: ignore[union-attr]
        self.assertEqual(markdown.status, "loaded")  # type: ignore[union-attr]
        store.dispatch({"kind": "ui", "artifact_group_by": "run"})
        run_rows = artifact_browser_rows(store.snapshot())
        self.assertEqual(run_rows[0].group_label, "task_1/run_2")
        store.dispatch({"kind": "ui", "artifact_group_by": "type"})
        type_rows = artifact_browser_rows(store.snapshot())
        self.assertEqual(type_rows[0].group_label, "text/markdown")

    def test_selected_markdown_artifact_projects_loading_and_failure_states(self) -> None:
        store = AppStateStore()
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
                                "display_name": "report.md",
                                "logical_path": "/workspace/artifacts/report.md",
                                "content_type": "text/markdown",
                                "created_at": "2026-03-12T00:00:05Z",
                            }
                        ]
                    }
                },
            }
        )
        store.dispatch({"kind": "ui", "markdown_viewer_artifact_id": "artifact_1"})
        loading_model = selected_markdown_artifact(store.snapshot())
        self.assertEqual(loading_model.status, "loading")  # type: ignore[union-attr]
        self.assertIn("Loading markdown artifact", loading_model.body)  # type: ignore[union-attr]
        store.dispatch(
            {
                "kind": "ui",
                "artifact_preview_artifact_id": "artifact_1",
                "artifact_preview_status": "failed",
                "artifact_preview_error": "preview exploded",
            }
        )
        failed_model = selected_markdown_artifact(store.snapshot())
        self.assertEqual(failed_model.status, "failed")  # type: ignore[union-attr]
        self.assertEqual(failed_model.error, "preview exploded")  # type: ignore[union-attr]

    def test_memory_inspect_groups_runtime_scopes_into_operator_views(self) -> None:
        store = AppStateStore()
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
                "name": "memory.inspect",
                "payload": {
                    "context": {"task_id": "task_1", "run_id": "run_1"},
                    "result": {
                        "entries": [
                            {
                                "memory_id": "scratch_1",
                                "scope": "scratch",
                                "namespace": "task.notes",
                                "summary": "Scratch note",
                                "content": '{"note":"hi"}',
                                "provenance": {"task_id": "task_1", "run_id": "run_1"},
                                "created_at": "2026-03-12T00:00:01Z",
                                "updated_at": "2026-03-12T00:00:02Z",
                                "source_run": "run_1",
                                "confidence": 0.8,
                            },
                            {
                                "memory_id": "run_1",
                                "scope": "run_state",
                                "namespace": "task.plan",
                                "summary": "Current plan",
                                "content": '{"step":"inspect"}',
                                "provenance": {"task_id": "task_1", "checkpoint": "cp-1"},
                                "created_at": "2026-03-12T00:00:03Z",
                                "updated_at": "2026-03-12T00:00:04Z",
                                "source_run": "run_1",
                            },
                            {
                                "memory_id": "proj_1",
                                "scope": "project",
                                "namespace": "repo",
                                "summary": "Project context",
                                "content": "Repository summary",
                                "provenance": {},
                                "created_at": "2026-03-12T00:00:05Z",
                                "updated_at": "2026-03-12T00:00:06Z",
                            },
                        ]
                    },
                },
            }
        )
        state = store.snapshot()
        groups = memory_scope_groups(state)
        counts = {group.group_id: group.count for group in groups}
        self.assertEqual(counts["short_term"], 1)
        self.assertEqual(counts["working_context"], 1)
        self.assertEqual(counts["episodic"], 1)
        self.assertEqual(counts["checkpoint_metadata"], 2)

        detail = selected_memory_detail(state)
        self.assertEqual(detail.status, "loaded")
        self.assertIn('"note": "hi"', detail.content)
        self.assertIn('"run_id": "run_1"', detail.provenance)

        summary = memory_group_summary(state)
        self.assertIn("Short-Term Memory", summary)
        self.assertIn("Read-only inspection", summary)

    def test_memory_selection_falls_back_after_refresh_and_projects_error_states(self) -> None:
        store = AppStateStore()
        store.dispatch(
            {
                "kind": "rpc",
                "name": "task.get",
                "payload": {
                    "result": {"task": {"task_id": "task_1", "run_id": "run_1", "status": "paused"}}
                },
            }
        )
        store.dispatch(
            {
                "kind": "rpc",
                "name": "memory.inspect",
                "payload": {
                    "context": {"task_id": "task_1", "run_id": "run_1"},
                    "result": {
                        "entries": [
                            {
                                "memory_id": "mem_1",
                                "scope": "project",
                                "namespace": "repo",
                                "summary": "Repository context",
                                "content": "alpha",
                                "provenance": {},
                                "created_at": "2026-03-12T00:00:01Z",
                                "updated_at": "2026-03-12T00:00:01Z",
                            }
                        ]
                    },
                },
            }
        )
        store.dispatch(
            {
                "kind": "ui",
                "selected_memory_group_id": "episodic",
                "selected_memory_entry_id": "mem_1",
            }
        )
        store.dispatch(
            {
                "kind": "rpc",
                "name": "memory.inspect",
                "payload": {
                    "context": {"task_id": "task_1", "run_id": "run_1"},
                    "result": {
                        "entries": [
                            {
                                "memory_id": "mem_2",
                                "scope": "scratch",
                                "namespace": "notes",
                                "summary": "Scratch note",
                                "content": "beta",
                                "provenance": {"task_id": "task_1"},
                                "created_at": "2026-03-12T00:00:02Z",
                                "updated_at": "2026-03-12T00:00:02Z",
                            }
                        ]
                    },
                },
            }
        )
        groups = memory_scope_groups(store.snapshot())
        self.assertTrue(
            any(group.group_id == "short_term" and group.count == 1 for group in groups)
        )
        entries = memory_entry_items(store.snapshot())
        self.assertEqual(entries[0].memory_id, "mem_2")

        store.dispatch(
            {
                "kind": "ui",
                "memory_request_status": "error",
                "memory_request_error": "runtime exploded",
            }
        )
        error_detail = selected_memory_detail(store.snapshot())
        self.assertEqual(error_detail.status, "error")
        self.assertIn("runtime exploded", error_detail.content)

    def test_config_selectors_project_sections_and_redactions(self) -> None:
        store = AppStateStore()
        store.dispatch(
            {
                "kind": "rpc",
                "name": "runtime.health",
                "payload": {
                    "result": {
                        "status": "ok",
                        "runtime_name": "demo-runtime",
                        "protocol_version": "1.0.0",
                        "identity": {"path": "/runtime/identity.json", "sha256": "abc123"},
                    }
                },
            }
        )
        store.dispatch(
            {
                "kind": "rpc",
                "name": "config.get",
                "payload": {
                    "result": {
                        "effective_config": {
                            "runtime": {"name": "demo-runtime", "log_level": "info"},
                            "transport": {"mode": "stdio-jsonrpc"},
                            "identity": {"path": "/runtime/identity.json"},
                            "models": {
                                "primary": {"provider": "openai", "model": "gpt-5-codex"},
                            },
                            "persistence": {"root_path": "/tmp/runtime"},
                            "cli": {"virtual_workspace_root": "/workspace"},
                            "policy": {"sandbox_mode": "workspace-write"},
                            "subagents": {"reviewer": {"role_id": "reviewer"}},
                        },
                        "loaded_profiles": ["default"],
                        "config_sources": ["docs/architecture/runtime.example.toml"],
                        "redactions": [{"path": "policy.api_token", "reason": "sensitive-key"}],
                    }
                },
            }
        )
        sections = config_section_items(store.snapshot())
        self.assertEqual(sections[0].section_id, "provider_settings")
        self.assertTrue(sections[0].is_selected)
        store.dispatch({"kind": "ui", "selected_config_section_id": "sandbox_policy"})
        detail = selected_config_detail(store.snapshot())
        self.assertEqual(detail.title, "Sandbox Policy")
        self.assertIn("policy.api_token", detail.body)
        self.assertIn("workspace-write", detail.body)

    def test_config_selector_surfaces_loading_and_error_states(self) -> None:
        store = AppStateStore()
        store.dispatch({"kind": "ui", "config_request_status": "loading"})
        loading = selected_config_detail(store.snapshot())
        self.assertEqual(loading.status, "loading")
        store.dispatch(
            {
                "kind": "ui",
                "config_request_status": "error",
                "config_request_error": "runtime exploded",
            }
        )
        error = selected_config_detail(store.snapshot())
        self.assertEqual(error.status, "error")
        self.assertIn("runtime exploded", error.body)

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
