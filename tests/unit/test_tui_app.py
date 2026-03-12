from __future__ import annotations

import unittest
from unittest.mock import patch

from apps.tui.local_agent_tui.app import _TEXTUAL_IMPORT_ERROR


class _FakeProtocolClient:
    def __init__(self, config_path: str) -> None:
        self.config_path = config_path

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
        return {
            "result": {
                "tasks": [
                    {
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "status": "executing",
                        "objective": "Inspect repo",
                        "created_at": "2026-03-12T00:00:00Z",
                        "updated_at": "2026-03-12T00:00:00Z",
                        "latest_summary": "Scanning repository",
                    },
                    {
                        "task_id": "task_2",
                        "run_id": "run_2",
                        "status": "paused",
                        "objective": "Review docs",
                        "created_at": "2026-03-11T00:00:00Z",
                        "updated_at": "2026-03-11T00:00:00Z",
                        "latest_summary": "Waiting for review",
                    },
                ]
            }
        }

    async def task_get(self, task_id: str, run_id: str | None = None) -> dict:
        tasks = {
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
            },
        }
        return {"result": {"task": tasks[task_id]}}

    async def task_approvals_list(self, task_id: str, run_id: str | None = None) -> dict:
        if task_id == "task_1":
            approvals = [
                {
                    "approval_id": "approval_1",
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "status": "pending",
                    "description": "tool permission",
                    "scope_summary": "filesystem.write",
                    "created_at": "2026-03-12T00:00:01Z",
                }
            ]
        elif task_id == "task_2":
            approvals = [
                {
                    "approval_id": "approval_2",
                    "task_id": "task_2",
                    "run_id": "run_2",
                    "status": "pending",
                    "description": "network permission",
                    "scope_summary": "network.fetch",
                    "created_at": "2026-03-11T00:00:01Z",
                }
            ]
        else:
            approvals = []
        return {"result": {"approvals": approvals}}

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


async def _fake_consume_task_stream(*args, **kwargs) -> None:
    return None


@unittest.skipIf(_TEXTUAL_IMPORT_ERROR is not None, "textual is not installed")
class TuiAppSmokeTests(unittest.IsolatedAsyncioTestCase):
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
