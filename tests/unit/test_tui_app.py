from __future__ import annotations

import asyncio
import threading
import unittest
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from apps.tui.local_agent_tui.app import _TEXTUAL_IMPORT_ERROR
from apps.tui.local_agent_tui.store.selectors import pending_approvals


_MARKDOWN_ARTIFACT_TEXT = """# Report

Summary body

## Findings

> Important context for the operator.

- first finding
- second finding

| Column | Value |
| --- | --- |
| status | ok |
| owner | agent |

---

```python
def render_report() -> str:
    return "Summary body"
```

## Appendix

Line 1
Line 2
Line 3
Line 4
Line 5
Line 6
Line 7
Line 8
Line 9
Line 10
Line 11
Line 12
Line 13
Line 14
Line 15
Line 16
Line 17
Line 18
Line 19
Line 20
Line 21
Line 22
Line 23
Line 24
Line 25
Line 26
Line 27
Line 28
Line 29
Line 30
Line 31
Line 32
Line 33
Line 34
Line 35
Line 36
Line 37
Line 38
Line 39
Line 40
Line 41
Line 42
Line 43
Line 44
Line 45
Line 46
Line 47
Line 48
Line 49
Line 50
Line 51
Line 52
Line 53
Line 54
Line 55
Line 56
Line 57
Line 58
Line 59
Line 60
"""


class _FakeProtocolClient:
    def __init__(self, config_path: str) -> None:
        self.config_path = config_path
        self.connect_calls = 0
        self.close_calls = 0
        self.resume_calls: list[tuple[str, str | None]] = []
        self.approve_calls: list[tuple[str | None, str | None, str, str]] = []
        self.approvals_list_calls: list[tuple[str, str | None]] = []
        self.artifact_get_calls: list[tuple[str, str | None, str]] = []
        self.memory_inspect_calls: list[tuple[str | None, str | None, str | None, str | None]] = []
        self.task_create_calls: list[tuple[str, list[str]]] = []
        self.diagnostics_list_calls: list[tuple[str, str | None]] = []
        self.get_config_calls = 0
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
        self._memory_entries: dict[str, list[dict[str, Any]]] = {
            "task_1": [
                {
                    "memory_id": "scratch_1",
                    "scope": "scratch",
                    "namespace": "task.notes",
                    "summary": "Scratch note",
                    "content": '{"note":"Summary body"}',
                    "provenance": {"task_id": "task_1", "run_id": "run_1"},
                    "created_at": "2026-03-12T00:00:03Z",
                    "updated_at": "2026-03-12T00:00:04Z",
                    "source_run": "run_1",
                    "confidence": 0.9,
                },
                {
                    "memory_id": "runstate_1",
                    "scope": "run_state",
                    "namespace": "task.plan",
                    "summary": "Current plan",
                    "content": '{"step":"Inspect repo"}',
                    "provenance": {"task_id": "task_1", "checkpoint": "cp-1"},
                    "created_at": "2026-03-12T00:00:05Z",
                    "updated_at": "2026-03-12T00:00:06Z",
                    "source_run": "run_1",
                },
                {
                    "memory_id": "project_1",
                    "scope": "project",
                    "namespace": "repo",
                    "summary": "Repository context",
                    "content": "Inspect repo",
                    "provenance": {},
                    "created_at": "2026-03-12T00:00:07Z",
                    "updated_at": "2026-03-12T00:00:08Z",
                },
            ]
        }
        self._config_payload = {
            "result": {
                "effective_config": {
                    "runtime": {"name": "demo-runtime", "log_level": "info"},
                    "transport": {"mode": "stdio-jsonrpc"},
                    "identity": {"path": "/runtime/identity.json"},
                    "models": {
                        "default": {"provider": "openai", "model": "gpt-5"},
                        "primary": {"provider": "openai", "model": "gpt-5-codex"},
                        "subagents": {"reviewer": {"provider": "openai", "model": "gpt-5-mini"}},
                        "resolved": {
                            "default": {
                                "provider": "openai",
                                "model": "gpt-5",
                                "profile_name": "default",
                                "source": "default_model",
                            }
                        },
                    },
                    "persistence": {
                        "root_path": "/tmp/runtime",
                        "metadata_backend": "sqlite",
                        "event_backend": "sqlite",
                        "diagnostic_backend": "sqlite",
                    },
                    "cli": {"default_workspace_root": "/workspace"},
                    "subagents": {
                        "reviewer": {
                            "role_id": "reviewer",
                            "model_profile": "default",
                            "resolved_model": {
                                "provider": "openai",
                                "model": "gpt-5-mini",
                                "profile_name": "reviewer",
                                "source": "subagent_override",
                            },
                            "tool_bindings": ["shell"],
                            "skills": ["checks"],
                        }
                    },
                    "policy": {"sandbox_mode": "workspace-write", "network_access": False},
                },
                "loaded_profiles": ["default"],
                "config_sources": ["docs/architecture/runtime.example.toml"],
                "redactions": [{"path": "policy.api_token", "reason": "sensitive-key"}],
            }
        }
        self._diagnostics: dict[str, list[dict[str, Any]]] = {
            "task_1": [
                {
                    "diagnostic_id": "diag_1",
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "kind": "runtime_error",
                    "message": "Task encountered a recoverable failure.",
                    "created_at": "2026-03-12T00:00:09Z",
                    "details": {"step": "tool.called", "code": "retryable"},
                }
            ],
            "task_2": [],
        }

    async def connect(self) -> None:
        self.connect_calls += 1
        return None

    async def close(self) -> None:
        self.close_calls += 1
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

    async def task_create(self, *, objective: str, workspace_roots: list[str]) -> dict:
        self.task_create_calls.append((objective, workspace_roots))
        task_id = f"task_{len(self._tasks) + 1}"
        run_id = f"run_{len(self._tasks) + 1}"
        self._tasks[task_id] = {
            "task_id": task_id,
            "run_id": run_id,
            "status": "accepted",
            "objective": objective,
            "created_at": "2026-03-12T00:00:10Z",
            "updated_at": "2026-03-12T00:00:10Z",
            "latest_summary": "Task accepted",
        }
        self._approvals[task_id] = []
        self._diagnostics[task_id] = []
        return {"result": {"task_id": task_id, "run_id": run_id, "status": "accepted"}}

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
                },
                {
                    "artifact_id": "artifact_2",
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "logical_path": "/artifacts/report.html",
                    "display_name": "report.html",
                    "content_type": "text/html",
                    "created_at": "2026-03-12T00:00:03Z",
                },
            ]
        else:
            artifacts = []
        return {"result": {"artifacts": artifacts}}

    async def task_artifact_get(
        self, task_id: str, artifact_id: str, run_id: str | None = None
    ) -> dict:
        self.artifact_get_calls.append((task_id, run_id, artifact_id))
        if artifact_id == "artifact_2":
            return {
                "result": {
                    "artifact": {
                        "artifact_id": artifact_id,
                        "task_id": task_id,
                        "run_id": run_id,
                        "logical_path": "/artifacts/report.html",
                        "display_name": "report.html",
                        "content_type": "text/html",
                        "created_at": "2026-03-12T00:00:03Z",
                    },
                    "preview": {
                        "kind": "text",
                        "text": "<html>summary</html>",
                        "encoding": "utf-8",
                    },
                    "external_open_supported": True,
                }
            }
        return {
            "result": {
                "artifact": {
                    "artifact_id": artifact_id,
                    "task_id": task_id,
                    "run_id": run_id,
                    "logical_path": "/artifacts/report.md",
                    "display_name": "report.md",
                    "content_type": "text/markdown",
                    "created_at": "2026-03-12T00:00:02Z",
                },
                "preview": {
                    "kind": "markdown",
                    "text": _MARKDOWN_ARTIFACT_TEXT,
                    "encoding": "utf-8",
                },
                "external_open_supported": False,
            }
        }

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

    async def memory_inspect(
        self,
        *,
        task_id: str | None = None,
        run_id: str | None = None,
        scope: str | None = None,
        namespace: str | None = None,
    ) -> dict:
        self.memory_inspect_calls.append((task_id, run_id, scope, namespace))
        entries = list(self._memory_entries.get(task_id or "", [])) if task_id is not None else []
        return {"result": {"entries": entries, "scope": scope or "default", "count": len(entries)}}

    async def get_config(self) -> dict:
        self.get_config_calls += 1
        return self._config_payload

    async def task_diagnostics_list(self, task_id: str, run_id: str | None = None) -> dict:
        self.diagnostics_list_calls.append((task_id, run_id))
        return {"result": {"diagnostics": list(self._diagnostics.get(task_id, []))}}


async def _fake_consume_task_stream(*args, **kwargs) -> None:
    return None


class _DelayedArtifactProtocolClient(_FakeProtocolClient):
    async def task_artifact_get(
        self, task_id: str, artifact_id: str, run_id: str | None = None
    ) -> dict:
        await asyncio.sleep(0.5)
        return await super().task_artifact_get(task_id, artifact_id, run_id)


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
        from textual.containers import VerticalScroll
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
                task_summary = app.screen.query_one("#task-summary", VerticalScroll)
                task_summary_content = app.screen.query_one("#task-summary-content", Static)
                artifacts = app.screen.query_one("#recent-artifacts", Static)
                approvals = app.screen.query_one("#approval-queue", Static)
                self.assertEqual(task_summary.border_title, "Selected Task")
                self.assertIn("Scanning repository", str(task_summary_content.visual))
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
                self.assertEqual(app._store.snapshot().focused_pane, "summary")  # type: ignore[attr-defined]
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

    async def test_command_palette_opens_filters_and_routes_to_diagnostics(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from apps.tui.local_agent_tui.store.selectors import selected_diagnostics_detail
        from textual.widgets import Input, Static

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
                await pilot.press("g")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "CommandPaletteScreen")
                palette_input = app.screen.query_one(Input)
                palette_input.value = "diag"
                app.handle_command_palette_query_changed("diag")  # type: ignore[attr-defined]
                await pilot.pause()
                results = app.screen.query_one("#command-palette-results", Static)
                self.assertIn("View diagnostics", str(results.visual))
                await pilot.press("enter")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "DiagnosticsScreen")
                detail = selected_diagnostics_detail(app._store.snapshot())  # type: ignore[attr-defined]
                self.assertIn("recoverable failure", detail.summary)

    async def test_command_palette_approve_request_opens_approval_workflow(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import Input

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
                await pilot.press("g")
                await pilot.pause()
                palette_input = app.screen.query_one(Input)
                palette_input.value = "approve"
                app.handle_command_palette_query_changed("approve")  # type: ignore[attr-defined]
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "ApprovalsScreen")
                self.assertEqual(app._store.snapshot().selected_approval_id, "approval_2")  # type: ignore[attr-defined]

    async def test_command_palette_opens_from_major_screens(self) -> None:
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
                app.action_back_dashboard()  # type: ignore[attr-defined]
                await pilot.pause()
                screen_openers = [
                    lambda: None,
                    app.action_open_task,  # type: ignore[attr-defined]
                    app.action_open_approvals,  # type: ignore[attr-defined]
                    app.action_open_artifacts,  # type: ignore[attr-defined]
                    app.action_open_memory,  # type: ignore[attr-defined]
                    app.action_open_config,  # type: ignore[attr-defined]
                    app.action_open_diagnostics,  # type: ignore[attr-defined]
                ]
                for open_screen in screen_openers:
                    app.action_back_dashboard()  # type: ignore[attr-defined]
                    await pilot.pause()
                    open_screen()
                    await pilot.pause()
                    app.action_open_command_palette()  # type: ignore[attr-defined]
                    await pilot.pause()
                    self.assertEqual(app.screen.__class__.__name__, "CommandPaletteScreen")
                    app.close_command_palette()  # type: ignore[attr-defined]
                    await pilot.pause()

    async def test_new_task_modal_submits_and_opens_task_detail(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import TextArea

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
                await pilot.press("n")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "CreateTaskScreen")
                create_input = app.screen.query_one(TextArea)
                create_input.load_text("Write a release note\nInclude customer-facing summary")
                app.submit_create_task(create_input.text)  # type: ignore[attr-defined]
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "TaskDetailScreen")
                self.assertEqual(app._store.snapshot().selected_task_id, "task_3")  # type: ignore[attr-defined]
                client = cast(_FakeProtocolClient, app._client)  # type: ignore[attr-defined]
                self.assertEqual(  # type: ignore[attr-defined]
                    client.task_create_calls[-1],
                    ("Write a release note\nInclude customer-facing summary", ["/workspace"]),
                )

    async def test_new_task_modal_enter_does_not_open_previous_selected_task(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import TextArea

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
                self.assertEqual(app._store.snapshot().selected_task_id, "task_1")  # type: ignore[attr-defined]
                await pilot.press("n")
                await pilot.pause()
                create_input = app.screen.query_one(TextArea)
                create_input.load_text("Create from modal\nWith multiple lines")
                app.submit_create_task(create_input.text)  # type: ignore[attr-defined]
                await pilot.pause()
                await pilot.pause()
                app._dispatch_and_render(  # type: ignore[attr-defined]
                    {
                        "kind": "rpc",
                        "name": "task.logs.stream",
                        "payload": {"result": {"task_id": "task_1", "run_id": "run_1"}},
                    }
                )
                await pilot.pause()
                self.assertEqual(app._store.snapshot().selected_task_id, "task_3")  # type: ignore[attr-defined]
                self.assertEqual(app.screen.__class__.__name__, "TaskDetailScreen")

    async def test_dashboard_selected_task_summary_scrolls_when_focused(self) -> None:
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
            async with app.run_test(size=(120, 28)) as pilot:
                await pilot.pause()
                app._store.dispatch(  # type: ignore[attr-defined]
                    {
                        "kind": "rpc",
                        "name": "task.get",
                        "payload": {
                            "result": {
                                "task": {
                                    "task_id": "task_1",
                                    "run_id": "run_1",
                                    "status": "executing",
                                    "objective": "Inspect repo\n"
                                    + "\n".join(f"Objective line {index}" for index in range(30)),
                                    "created_at": "2026-03-12T00:00:00Z",
                                    "updated_at": "2026-03-12T00:00:00Z",
                                    "latest_summary": "\n".join(
                                        f"Summary line {index}" for index in range(40)
                                    ),
                                }
                            }
                        },
                    }
                )
                app._render_state()  # type: ignore[attr-defined]
                await pilot.pause()
                await pilot.press("tab")
                await pilot.pause()
                self.assertEqual(app._store.snapshot().focused_pane, "summary")  # type: ignore[attr-defined]
                summary_pane = app.screen.query_one("#task-summary")
                self.assertEqual(summary_pane.scroll_y, 0.0)
                await pilot.press("down")
                await pilot.pause()
                self.assertGreater(summary_pane.scroll_y, 0.0)
                await pilot.press("up")
                await pilot.pause()
                self.assertEqual(summary_pane.scroll_y, 0.0)

    async def test_create_task_modal_resets_text_and_status_between_opens(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import Static, TextArea

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
                await pilot.press("n")
                await pilot.pause()
                create_input = app.screen.query_one(TextArea)
                status = app.screen.query_one("#create-task-status", Static)
                create_input.load_text("Stale objective")
                app.screen.set_status("Objective is required.")  # type: ignore[attr-defined]
                await pilot.press("escape")
                await pilot.pause()
                await pilot.press("n")
                await pilot.pause()
                create_input = app.screen.query_one(TextArea)
                status = app.screen.query_one("#create-task-status", Static)
                self.assertEqual(create_input.text, "")
                self.assertIn("Ctrl+Enter submits", str(status.visual))

    async def test_markdown_viewer_keeps_local_g_binding_instead_of_command_palette(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from apps.tui.local_agent_tui.widgets.markdown_viewer import MarkdownViewerWidget

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
                await pilot.press("o")
                await pilot.pause()
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                viewer = app.screen.query_one(MarkdownViewerWidget)
                await pilot.press("shift+g")
                await pilot.pause()
                self.assertGreater(viewer.scroll_y, 0.0)
                await pilot.press("g")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "MarkdownViewerScreen")
                self.assertEqual(viewer.scroll_y, 0.0)

    async def test_task_detail_opens_artifact_browser_and_markdown_viewer(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from apps.tui.local_agent_tui.widgets.markdown_viewer import MarkdownViewerWidget
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
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "ArtifactsScreen")
                await pilot.press("r")
                await pilot.pause()
                self.assertEqual(app._store.snapshot().artifact_group_by, "run")  # type: ignore[attr-defined]
                self.assertIn(
                    "Summary body",
                    app._store.snapshot().artifact_preview_cache["artifact_1"]["preview"]["text"],  # type: ignore[attr-defined]
                )
                await pilot.press("enter")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "MarkdownViewerScreen")
                self.assertEqual(
                    app._store.snapshot().markdown_viewer_artifact_id,  # type: ignore[attr-defined]
                    "artifact_1",
                )
                viewer = app.screen.query_one(MarkdownViewerWidget)
                self.assertIn("Summary body", viewer._source_text)
                await pilot.press("q")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "ArtifactsScreen")
                await pilot.press("enter")
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "ArtifactsScreen")
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "TaskDetailScreen")
                self.assertEqual(
                    app._client.artifact_get_calls[-1],  # type: ignore[attr-defined]
                    ("task_1", "run_1", "artifact_1"),
                )

    async def test_artifacts_screen_supports_external_open(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import Static

        class _FakeProcess:
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                return (b"", b"")

        with (
            patch("apps.tui.local_agent_tui.app.ProtocolClient", _FakeProtocolClient),
            patch("apps.tui.local_agent_tui.app.consume_task_stream", _fake_consume_task_stream),
            patch(
                "apps.tui.local_agent_tui.app.asyncio.create_subprocess_exec",
                AsyncMock(return_value=_FakeProcess()),
            ) as open_mock,
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
                await pilot.press("o")
                await pilot.pause()
                await pilot.pause()
                app.handle_artifact_browser_selected("artifact_2")  # type: ignore[attr-defined]
                await pilot.pause()
                await pilot.pause()
                await pilot.press("e")
                await pilot.pause()
                footer = app.screen.query_one("#artifacts-screen-footer", Static)
                self.assertIn("Opened /artifacts/report.html.", str(footer.visual))
                open_mock.assert_awaited()

    async def test_markdown_viewer_scroll_and_search_bindings(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from apps.tui.local_agent_tui.screens.markdown_viewer import MarkdownViewerScreen
        from apps.tui.local_agent_tui.widgets.markdown_viewer import MarkdownViewerWidget
        from textual.widgets import Input, Static

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
                await pilot.press("o")
                await pilot.pause()
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                viewer = app.screen.query_one(MarkdownViewerWidget)
                self.assertEqual(viewer.scroll_y, 0.0)
                self.assertIsInstance(app.screen, MarkdownViewerScreen)
                await pilot.press("shift+g")
                await pilot.pause()
                self.assertGreater(viewer.scroll_y, 0.0)
                await pilot.press("g")
                await pilot.pause()
                self.assertEqual(viewer.scroll_y, 0.0)
                await pilot.press("/")
                await pilot.pause()
                search_input = app.screen.query_one(Input)
                search_input.value = "summary body"
                await search_input.action_submit()
                await pilot.pause()
                footer = app.screen.query_one("#markdown-viewer-footer", Static)
                self.assertIn("summary body", str(footer.visual).lower())
                self.assertEqual(viewer.search_state.query, "summary body")
                self.assertGreaterEqual(viewer.search_state.total_matches, 1)

    async def test_markdown_viewer_shows_loading_until_preview_arrives(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from apps.tui.local_agent_tui.store.selectors import selected_markdown_artifact

        with (
            patch("apps.tui.local_agent_tui.app.ProtocolClient", _DelayedArtifactProtocolClient),
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
                app.action_open_artifacts()  # type: ignore[attr-defined]
                await pilot.pause()
                app.action_open_task()  # type: ignore[attr-defined]
                await pilot.pause()
                loading_model = selected_markdown_artifact(app._store.snapshot())  # type: ignore[attr-defined]
                self.assertIsNotNone(loading_model)
                self.assertEqual(loading_model.status, "loading")  # type: ignore[union-attr]
                await asyncio.sleep(0.6)
                await pilot.pause()
                loaded_model = selected_markdown_artifact(app._store.snapshot())  # type: ignore[attr-defined]
                self.assertEqual(loaded_model.status, "loaded")  # type: ignore[union-attr]
                self.assertIn("Summary body", loaded_model.body)  # type: ignore[union-attr]

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

    async def test_task_detail_command_input_dispatches_commands(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import Input, Static

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
                await pilot.press("i")
                await pilot.pause()
                command_input = app.screen.query_one(Input)
                command_input.value = "resume"
                await command_input.action_submit()
                await pilot.pause()
                status = app.screen.query_one("#task-detail-command-status", Static)
                self.assertIn("Ran 'resume'.", str(status.visual))
                self.assertEqual(app._client.resume_calls[-1], ("task_2", "run_2"))  # type: ignore[attr-defined]

    async def test_task_detail_timeline_filter_and_search_prompts_update_state(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from textual.widgets import Input, Static

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
                app._store.dispatch(  # type: ignore[attr-defined]
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
                app._store.dispatch(  # type: ignore[attr-defined]
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
                await pilot.press("enter")
                await pilot.pause()
                await pilot.press("f")
                await pilot.pause()
                filter_input = app.screen.query_one(Input)
                filter_input.value = "tools"
                await filter_input.action_submit()
                await pilot.pause()
                footer = app.screen.query_one("#task-detail-footer", Static)
                self.assertIn("Timeline filter: tools", str(footer.visual))
                timeline = app.screen.query_one("#task-detail-timeline", Static)
                self.assertIn("shell", str(timeline.visual))
                self.assertNotIn("Approval requested", str(timeline.visual))
                await pilot.press("/")
                await pilot.pause()
                search_input = app.screen.query_one(Input)
                search_input.value = "shell"
                await search_input.action_submit()
                await pilot.pause()
                footer = app.screen.query_one("#task-detail-footer", Static)
                self.assertIn("Search: shell", str(footer.visual))

    async def test_reconnect_runtime_restores_context(self) -> None:
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
                original_client = app._client  # type: ignore[attr-defined]
                await app._reconnect_runtime()  # type: ignore[attr-defined]
                self.assertEqual(app.screen.__class__.__name__, "TaskDetailScreen")
                self.assertEqual(app._store.snapshot().selected_task_id, "task_1")  # type: ignore[attr-defined]
                self.assertNotEqual(app._client, original_client)  # type: ignore[attr-defined]
                self.assertGreater(original_client.close_calls, 0)  # type: ignore[attr-defined]
                self.assertGreater(app._client.connect_calls, 0)  # type: ignore[attr-defined]

    async def test_memory_screen_opens_renders_and_returns_to_origin(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from apps.tui.local_agent_tui.store.selectors import (
            memory_scope_groups,
            selected_memory_detail,
        )

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
                await pilot.press("m")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "MemoryScreen")
                self.assertEqual(
                    app._client.memory_inspect_calls[-1],  # type: ignore[attr-defined]
                    ("task_1", "run_1", None, None),
                )
                self.assertTrue(
                    any(group.count > 0 for group in memory_scope_groups(app._store.snapshot()))
                )  # type: ignore[attr-defined]
                self.assertIn(
                    "Scratch note",
                    selected_memory_detail(app._store.snapshot()).summary,  # type: ignore[attr-defined]
                )
                app._store.dispatch({"kind": "ui", "focused_pane": "memory_entries"})  # type: ignore[attr-defined]
                app.handle_memory_group_selected("working_context")  # type: ignore[attr-defined]
                app.handle_memory_entry_selected("runstate_1")  # type: ignore[attr-defined]
                app._render_state()  # type: ignore[attr-defined]
                self.assertIn(
                    "Current plan",
                    selected_memory_detail(app._store.snapshot()).summary,  # type: ignore[attr-defined]
                )
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "DashboardScreen")

    async def test_memory_screen_opens_from_task_detail_without_interrupting_stream(self) -> None:
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
                detail_stream_key = app._stream_key  # type: ignore[attr-defined]
                await pilot.press("m")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "MemoryScreen")
                self.assertEqual(app._stream_key, detail_stream_key)  # type: ignore[attr-defined]
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "TaskDetailScreen")
                self.assertEqual(app._stream_key, detail_stream_key)  # type: ignore[attr-defined]

    async def test_memory_screen_refresh_does_not_lose_origin_screen(self) -> None:
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
            app._store.dispatch(  # type: ignore[attr-defined]
                {
                    "kind": "rpc",
                    "name": "task.get",
                    "payload": {"result": {"task": app._client._tasks["task_1"]}},  # type: ignore[attr-defined]
                }
            )
            app._store.dispatch(  # type: ignore[attr-defined]
                {
                    "kind": "ui",
                    "selected_task_id": "task_1",
                    "active_screen": "memory",
                    "memory_origin_screen": "task_detail",
                }
            )
            scheduled: list[object] = []
            switched: list[object] = []
            app._render_state = lambda: None  # type: ignore[method-assign]

            def _switch_screen(name: object) -> Any:
                switched.append(name)
                return None

            app.switch_screen = _switch_screen  # type: ignore[assignment,method-assign]

            def _run_worker(coro: object, **_: object) -> None:
                scheduled.append(coro)
                close = getattr(coro, "close", None)
                if callable(close):
                    close()

            app.run_worker = _run_worker  # type: ignore[assignment,method-assign]

            app._open_memory_inspector()  # type: ignore[attr-defined]

            state = app._store.snapshot()  # type: ignore[attr-defined]
            self.assertEqual(state.memory_origin_screen, "task_detail")
            self.assertEqual(state.active_screen, "memory")
            self.assertEqual(switched, [])
            self.assertEqual(len(scheduled), 1)

    async def test_config_screen_opens_renders_and_returns_to_origin(self) -> None:
        from apps.tui.local_agent_tui.app import AgentTUI
        from apps.tui.local_agent_tui.store.selectors import selected_config_detail
        from apps.tui.local_agent_tui.widgets.config_detail import ConfigDetailWidget
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
                await pilot.press("c")
                await pilot.pause()
                await pilot.pause()
                app._render_state()  # type: ignore[attr-defined]
                self.assertEqual(app.screen.__class__.__name__, "ConfigScreen")
                self.assertEqual(app._client.get_config_calls, 1)  # type: ignore[attr-defined]
                detail = app.screen.query_one(ConfigDetailWidget)
                footer = app.screen.query_one("#config-screen-footer", Static)
                detail_model = selected_config_detail(app._store.snapshot())  # type: ignore[attr-defined]
                self.assertEqual(detail_model.title, "Provider Settings")
                self.assertIn("provider-adjacent settings", detail_model.summary)
                self.assertIn('"runtime"', detail_model.body)
                self.assertIn("Status: loaded", str(detail.visual))
                self.assertIn("read-only", str(footer.visual))
                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(
                    app._store.snapshot().selected_config_section_id,  # type: ignore[attr-defined]
                    "sandbox_policy",
                )
                self.assertIn(
                    "redactions",
                    selected_config_detail(app._store.snapshot()).body,  # type: ignore[attr-defined]
                )
                app.action_move_down()  # type: ignore[attr-defined]
                await pilot.pause()
                workspace_detail = selected_config_detail(app._store.snapshot())  # type: ignore[attr-defined]
                self.assertEqual(workspace_detail.title, "Workspace Context")
                self.assertIn("/workspace", workspace_detail.body)
                await pilot.press("down")
                await pilot.pause()
                identity_detail = selected_config_detail(app._store.snapshot())  # type: ignore[attr-defined]
                self.assertEqual(identity_detail.title, "Runtime Identity")
                self.assertIn("/runtime/identity.json", identity_detail.body)
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "DashboardScreen")

    async def test_config_screen_opens_from_task_detail_and_refreshes_without_interrupting_stream(
        self,
    ) -> None:
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
                detail_stream_key = app._stream_key  # type: ignore[attr-defined]
                await pilot.press("c")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "ConfigScreen")
                self.assertEqual(app._stream_key, detail_stream_key)  # type: ignore[attr-defined]
                self.assertEqual(app._client.get_config_calls, 1)  # type: ignore[attr-defined]
                await app._refresh_config()  # type: ignore[attr-defined]
                self.assertEqual(app._stream_key, detail_stream_key)  # type: ignore[attr-defined]
                self.assertEqual(
                    app._store.snapshot().config_request_status,  # type: ignore[attr-defined]
                    "loaded",
                )
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "TaskDetailScreen")
                self.assertEqual(app._stream_key, detail_stream_key)  # type: ignore[attr-defined]
