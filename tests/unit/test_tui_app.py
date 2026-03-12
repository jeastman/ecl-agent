from __future__ import annotations

import threading
import unittest
from typing import Any
from unittest.mock import patch

from apps.tui.local_agent_tui.app import _TEXTUAL_IMPORT_ERROR
from apps.tui.local_agent_tui.store.selectors import pending_approvals


class _FakeProtocolClient:
    def __init__(self, config_path: str) -> None:
        self.config_path = config_path
        self.resume_calls: list[tuple[str, str | None]] = []
        self.approve_calls: list[tuple[str | None, str | None, str, str]] = []
        self.approvals_list_calls: list[tuple[str, str | None]] = []
        self._tasks: dict[str, dict[str, Any]] = {
            "task_1": {
                "task_id": "task_1",
                "run_id": "run_1",
                "status": "executing",
                "objective": "Inspect repo",
                "created_at": "2026-03-12T00:00:00Z",
                "updated_at": "2026-03-12T00:00:00Z",
                "latest_summary": "Scanning repository",
            },
            "task_2": {
                "task_id": "task_2",
                "run_id": "run_2",
                "status": "paused",
                "objective": "Review docs",
                "created_at": "2026-03-11T00:00:00Z",
                "updated_at": "2026-03-11T00:00:00Z",
                "latest_summary": "Waiting for review",
                "is_resumable": True,
                "links": {"resume": "task.resume"},
            },
        }
        self._approvals: dict[str, list[dict[str, Any]]] = {
            "task_1": [
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
                    "description": "tool permission",
                    "scope_summary": "filesystem.write",
                    "created_at": "2026-03-12T00:00:01Z",
                }
            ],
            "task_2": [
                {
                    "approval_id": "approval_2",
                    "task_id": "task_2",
                    "run_id": "run_2",
                    "status": "pending",
                    "type": "skill_install",
                    "scope": {
                        "kind": "skill.install",
                        "target_scope": "skills/demo",
                    },
                    "description": "network permission",
                    "scope_summary": "network.fetch",
                    "created_at": "2026-03-11T00:00:01Z",
                }
            ],
        }

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def runtime_health(self) -> dict:
        return {
            "result": {
                "status": "ok",
                "runtime_name": "demo-runtime",
                "transport": "stdio-jsonrpc",
            }
        }

    async def task_list(self, *, limit: int | None = None) -> dict:
        return {"result": {"tasks": list(self._tasks.values())}}

    async def task_get(self, task_id: str, run_id: str | None = None) -> dict:
        return {"result": {"task": self._tasks[task_id]}}

    async def task_approvals_list(self, task_id: str, run_id: str | None = None) -> dict:
        self.approvals_list_calls.append((task_id, run_id))
        return {"result": {"approvals": list(self._approvals.get(task_id, []))}}

    async def task_artifacts_list(self, task_id: str, run_id: str | None = None) -> dict:
        if task_id == "task_1":
            artifacts = [
                {
                    "artifact_id": "artifact_1",
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "logical_path": "/artifacts/report.md",
                    "display_name": "report.md",
                    "content_type": "text/markdown",
                    "created_at": "2026-03-12T00:00:02Z",
                }
            ]
        else:
            artifacts = []
        return {"result": {"artifacts": artifacts}}

    async def task_resume(self, task_id: str, run_id: str | None = None) -> dict:
        self.resume_calls.append((task_id, run_id))
        self._tasks[task_id] = {
            **self._tasks[task_id],
            "status": "executing",
            "updated_at": "2026-03-12T00:00:00Z",
            "latest_summary": "Resumed task",
        }
        return {"result": {"task": self._tasks[task_id]}}

    async def task_approve(
        self,
        task_id: str | None,
        run_id: str | None,
        approval_id: str,
        decision: str,
    ) -> dict:
        self.approve_calls.append((task_id, run_id, approval_id, decision))
        assert task_id is not None
        task = self._tasks[task_id]
        self._tasks[task_id] = {
            **task,
            "status": "executing",
            "updated_at": "2026-03-12T00:00:05Z",
            "latest_summary": f"{decision} {approval_id}",
            "awaiting_approval": False,
            "pending_approval_id": None,
        }
        updated_approvals: list[dict] = []
        for approval in self._approvals.get(task_id, []):
            if approval["approval_id"] == approval_id:
                updated_approvals.append({**approval, "status": decision})
            else:
                updated_approvals.append(approval)
        self._approvals[task_id] = updated_approvals
        return {
            "result": {
                "approval_id": approval_id,
                "accepted": True,
                "status": decision,
                "task": self._tasks[task_id],
            }
        }


async def _fake_consume_task_stream(*args, **kwargs) -> None:
    return None


@unittest.skipIf(_TEXTUAL_IMPORT_ERROR is not None, "textual is not installed")
class TuiAppSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_and_render_uses_direct_render_on_app_thread(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI

        with patch("apps.tui.local_agent_tui.app.ProtocolClient", _FakeProtocolClient):
            app = AgentTUI(
                config_path="docs/architecture/runtime.example.toml",
                task_id=None,
                run_id=None,
            )
            rendered: list[str] = []
            app._render_state = lambda: rendered.append("rendered")  # type: ignore[method-assign]

            def _call_from_thread(callback: Any, *args: Any, **kwargs: Any) -> Any:
                raise AssertionError("call_from_thread should not be used on the app thread")

            app.call_from_thread = _call_from_thread  # type: ignore[assignment,method-assign]
            app._thread_id = threading.get_ident()  # type: ignore[attr-defined]

            app._dispatch_and_render({"kind": "connection", "status": "connected"})  # type: ignore[arg-type]

            self.assertEqual(rendered, ["rendered"])
            self.assertEqual(app._store.snapshot().connection_status, "connected")  # type: ignore[attr-defined]

    async def test_dashboard_is_default_screen_and_shows_dashboard_content(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import Static

        with (
            patch("apps.tui.local_agent_tui.app.ProtocolClient", _FakeProtocolClient),
            patch("apps.tui.local_agent_tui.app.consume_task_stream", _fake_consume_task_stream),
        ):
            app = AgentTUI(
                config_path="docs/architecture/runtime.example.toml",
                task_id=None,
                run_id=None,
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                app._render_state()  # type: ignore[attr-defined]
                self.assertEqual(app.screen.__class__.__name__, "DashboardScreen")
                self.assertEqual(app._store.snapshot().selected_task_id, "task_1")  # type: ignore[attr-defined]
                task_summary = app.screen.query_one("#task-summary", Static)
                artifacts = app.screen.query_one("#recent-artifacts", Static)
                approvals = app.screen.query_one("#approval-queue", Static)
                self.assertIn("Scanning repository", str(task_summary.visual))
                self.assertIn("report.md", str(artifacts.visual))
                self.assertIn("tool permission", str(approvals.visual))

    async def test_dashboard_keyboard_navigation_updates_selection_and_focus(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI

        with (
            patch("apps.tui.local_agent_tui.app.ProtocolClient", _FakeProtocolClient),
            patch("apps.tui.local_agent_tui.app.consume_task_stream", _fake_consume_task_stream),
        ):
            app = AgentTUI(
                config_path="docs/architecture/runtime.example.toml",
                task_id=None,
                run_id=None,
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(app._store.snapshot().selected_task_id, "task_2")  # type: ignore[attr-defined]
                await pilot.press("tab")
                await pilot.pause()
                self.assertEqual(app._store.snapshot().focused_pane, "approvals")  # type: ignore[attr-defined]
                self.assertEqual(app._store.snapshot().selected_approval_id, "approval_1")  # type: ignore[attr-defined]
                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(app._store.snapshot().selected_approval_id, "approval_2")  # type: ignore[attr-defined]

    async def test_open_task_and_approvals_routes_from_dashboard(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI

        with (
            patch("apps.tui.local_agent_tui.app.ProtocolClient", _FakeProtocolClient),
            patch("apps.tui.local_agent_tui.app.consume_task_stream", _fake_consume_task_stream),
        ):
            app = AgentTUI(
                config_path="docs/architecture/runtime.example.toml",
                task_id=None,
                run_id=None,
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "TaskDetailScreen")
                await pilot.press("escape")
                await pilot.pause()
                await pilot.press("tab")
                await pilot.pause()
                await pilot.press("down")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "ApprovalsScreen")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "TaskDetailScreen")
                self.assertEqual(app._store.snapshot().selected_task_id, "task_2")  # type: ignore[attr-defined]
                await pilot.press("a")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "ApprovalsScreen")
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "DashboardScreen")

    async def test_approvals_screen_renders_detail_and_submits_decisions(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import Static

        with (
            patch("apps.tui.local_agent_tui.app.ProtocolClient", _FakeProtocolClient),
            patch("apps.tui.local_agent_tui.app.consume_task_stream", _fake_consume_task_stream),
        ):
            app = AgentTUI(
                config_path="docs/architecture/runtime.example.toml",
                task_id=None,
                run_id=None,
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()
                app._render_state()  # type: ignore[attr-defined]
                detail = app.screen.query_one("#approvals-screen-detail", Static)
                footer = app.screen.query_one("#approvals-screen-footer", Static)
                self.assertIn("Policy: sandbox", str(detail.visual))
                self.assertIn("Action: /workspace/docs/spec.md", str(detail.visual))
                self.assertIn("Approve", str(footer.visual))
                await pilot.press("a")
                await pilot.pause()
                footer = app.screen.query_one("#approvals-screen-footer", Static)
                self.assertEqual(
                    app._client.approve_calls[-1],  # type: ignore[attr-defined]
                    ("task_1", "run_1", "approval_1", "approved"),
                )
                self.assertEqual(app._store.snapshot().selected_approval_id, "approval_2")  # type: ignore[attr-defined]
                self.assertIn("Approved approval_1.", str(footer.visual))

    async def test_approvals_screen_rejects_request_and_keeps_feedback(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import Static

        with (
            patch("apps.tui.local_agent_tui.app.ProtocolClient", _FakeProtocolClient),
            patch("apps.tui.local_agent_tui.app.consume_task_stream", _fake_consume_task_stream),
        ):
            app = AgentTUI(
                config_path="docs/architecture/runtime.example.toml",
                task_id=None,
                run_id=None,
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()
                await pilot.press("r")
                await pilot.pause()
                footer = app.screen.query_one("#approvals-screen-footer", Static)
                self.assertEqual(
                    app._client.approve_calls[-1],  # type: ignore[attr-defined]
                    ("task_1", "run_1", "approval_1", "rejected"),
                )
                self.assertIn("Rejected approval_1.", str(footer.visual))

    async def test_opening_approvals_refreshes_known_task_approval_lists(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import Static

        with (
            patch("apps.tui.local_agent_tui.app.ProtocolClient", _FakeProtocolClient),
            patch("apps.tui.local_agent_tui.app.consume_task_stream", _fake_consume_task_stream),
        ):
            app = AgentTUI(
                config_path="docs/architecture/runtime.example.toml",
                task_id=None,
                run_id=None,
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                app._client._approvals["task_2"].append(  # type: ignore[attr-defined]
                    {
                        "approval_id": "approval_3",
                        "task_id": "task_2",
                        "run_id": "run_2",
                        "status": "pending",
                        "type": "boundary",
                        "scope": {
                            "boundary_key": "external",
                            "path_scope": "/tmp/out.txt",
                        },
                        "description": "filesystem permission",
                        "scope_summary": "filesystem.write",
                        "created_at": "2026-03-12T00:00:06Z",
                    }
                )
                await pilot.press("a")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app._store.snapshot().selected_approval_id, "approval_1")  # type: ignore[attr-defined]
                self.assertIn(
                    "approval_3",
                    [item.approval_id for item in pending_approvals(app._store.snapshot())],  # type: ignore[attr-defined]
                )
                self.assertGreaterEqual(len(app._client.approvals_list_calls), 4)  # type: ignore[attr-defined]

    async def test_approvals_screen_empty_state_after_last_decision(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import Static

        with (
            patch("apps.tui.local_agent_tui.app.ProtocolClient", _FakeProtocolClient),
            patch("apps.tui.local_agent_tui.app.consume_task_stream", _fake_consume_task_stream),
        ):
            app = AgentTUI(
                config_path="docs/architecture/runtime.example.toml",
                task_id=None,
                run_id=None,
            )
            app._client._approvals["task_2"] = []  # type: ignore[attr-defined]
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()
                queue = app.screen.query_one("#approvals-screen-queue", Static)
                detail = app.screen.query_one("#approvals-screen-detail", Static)
                self.assertIn("No pending approvals.", str(queue.visual))
                self.assertIn("Select an approval", str(detail.visual))

    async def test_task_detail_renders_phase3_panels_and_artifact_selection(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import Static

        with (
            patch("apps.tui.local_agent_tui.app.ProtocolClient", _FakeProtocolClient),
            patch("apps.tui.local_agent_tui.app.consume_task_stream", _fake_consume_task_stream),
        ):
            app = AgentTUI(
                config_path="docs/architecture/runtime.example.toml",
                task_id=None,
                run_id=None,
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                app._render_state()  # type: ignore[attr-defined]
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "TaskDetailScreen")
                header = app.screen.query_one("#task-detail-header", Static)
                timeline = app.screen.query_one("#task-detail-timeline", Static)
                plan = app.screen.query_one("#task-detail-plan", Static)
                artifacts = app.screen.query_one("#task-detail-artifacts", Static)
                self.assertIn("task_1", str(header.visual))
                self.assertIn("No events yet.", str(timeline.visual))
                self.assertIn("Scanning repository", str(plan.visual))
                self.assertIn("report.md", str(artifacts.visual))
                await pilot.press("o")
                await pilot.pause()
                self.assertIn(">", str(artifacts.visual))

    async def test_task_detail_resume_action_updates_store(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI

        with (
            patch("apps.tui.local_agent_tui.app.ProtocolClient", _FakeProtocolClient),
            patch("apps.tui.local_agent_tui.app.consume_task_stream", _fake_consume_task_stream),
        ):
            app = AgentTUI(
                config_path="docs/architecture/runtime.example.toml",
                task_id=None,
                run_id=None,
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("down")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                await pilot.press("r")
                await pilot.pause()
                self.assertEqual(
                    app._store.snapshot().task_snapshots["task_2"]["status"], "executing"
                )  # type: ignore[attr-defined]
                self.assertEqual(app._client.resume_calls[-1], ("task_2", "run_2"))  # type: ignore[attr-defined]
