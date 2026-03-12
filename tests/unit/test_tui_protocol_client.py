from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock
from unittest.mock import patch

from apps.tui.local_agent_tui.protocol.event_stream import consume_task_stream
from apps.tui.local_agent_tui.protocol.protocol_client import ProtocolClient, ProtocolClientError


class TuiProtocolClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_route_payload_sends_responses_to_pending_future(self) -> None:
        client = ProtocolClient("docs/architecture/runtime.example.toml")
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        client._pending["1"] = future  # type: ignore[attr-defined]
        client._route_payload({"id": "1", "result": {"status": "ok"}})  # type: ignore[attr-defined]
        self.assertEqual((await future)["result"]["status"], "ok")

    async def test_route_payload_queues_runtime_events(self) -> None:
        client = ProtocolClient("docs/architecture/runtime.example.toml")
        client._route_payload({"type": "runtime.event", "event": {"event_type": "task.started"}})  # type: ignore[attr-defined]
        event = await client.next_event()
        self.assertEqual(event["event"]["event_type"], "task.started")

    async def test_route_payload_surfaces_json_rpc_errors(self) -> None:
        client = ProtocolClient("docs/architecture/runtime.example.toml")
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        client._pending["1"] = future  # type: ignore[attr-defined]
        client._route_payload({"id": "1", "error": {"code": -1, "message": "boom"}})  # type: ignore[attr-defined]
        with self.assertRaises(ProtocolClientError):
            await future

    async def test_parse_payload_rejects_invalid_json(self) -> None:
        client = ProtocolClient("docs/architecture/runtime.example.toml")
        with self.assertRaises(ProtocolClientError):
            client._parse_payload("{")  # type: ignore[attr-defined]

    async def test_task_list_uses_protocol_method(self) -> None:
        client = ProtocolClient("docs/architecture/runtime.example.toml")
        request_mock = AsyncMock(return_value={"result": {"tasks": []}})
        with patch.object(client, "_request", request_mock):
            payload = await client.task_list(limit=5)
        self.assertEqual(payload["result"]["tasks"], [])
        request_mock.assert_awaited_once_with("task.list", {"limit": 5})

    async def test_memory_inspect_uses_protocol_method(self) -> None:
        client = ProtocolClient("docs/architecture/runtime.example.toml")
        request_mock = AsyncMock(return_value={"result": {"entries": []}})
        with patch.object(client, "_request", request_mock):
            payload = await client.memory_inspect(task_id="task_1", run_id="run_1")
        self.assertEqual(payload["result"]["entries"], [])
        request_mock.assert_awaited_once_with(
            "memory.inspect",
            {"task_id": "task_1", "run_id": "run_1"},
        )

    async def test_task_resume_uses_protocol_method(self) -> None:
        client = ProtocolClient("docs/architecture/runtime.example.toml")
        request_mock = AsyncMock(return_value={"result": {"task": {"task_id": "task_1"}}})
        with patch.object(client, "_request", request_mock):
            payload = await client.task_resume("task_1", "run_1")
        self.assertEqual(payload["result"]["task"]["task_id"], "task_1")
        request_mock.assert_awaited_once_with(
            "task.resume", {"task_id": "task_1", "run_id": "run_1"}
        )

    async def test_task_artifact_get_uses_protocol_method(self) -> None:
        client = ProtocolClient("docs/architecture/runtime.example.toml")
        request_mock = AsyncMock(
            return_value={"result": {"artifact": {"artifact_id": "artifact_1"}}}
        )
        with patch.object(client, "_request", request_mock):
            payload = await client.task_artifact_get("task_1", "artifact_1", "run_1")
        self.assertEqual(payload["result"]["artifact"]["artifact_id"], "artifact_1")
        request_mock.assert_awaited_once_with(
            "task.artifact.get",
            {"task_id": "task_1", "artifact_id": "artifact_1", "run_id": "run_1"},
        )

    async def test_consume_task_stream_filters_other_tasks_and_stops_on_selected_terminal_event(
        self,
    ) -> None:
        class _FakeClient:
            def __init__(self) -> None:
                self.events: asyncio.Queue[dict[str, object]] = asyncio.Queue()

            async def task_logs_stream(
                self, task_id: str, run_id: str | None, *, include_history: bool
            ) -> dict:
                return {"result": {"task_id": task_id, "run_id": run_id, "stream_open": True}}

            async def next_event(self) -> dict:
                return await self.events.get()

        client = _FakeClient()
        dispatched: list[dict] = []

        await client.events.put(
            {
                "event": {
                    "task_id": "task_2",
                    "run_id": "run_2",
                    "event_type": "task.completed",
                    "payload": {},
                }
            }
        )
        await client.events.put(
            {
                "event": {
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "event_type": "plan.updated",
                    "payload": {"summary": "step"},
                }
            }
        )
        await client.events.put(
            {
                "event": {
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "event_type": "task.completed",
                    "payload": {},
                }
            }
        )

        await consume_task_stream(
            client,  # type: ignore[arg-type]
            task_id="task_1",
            run_id="run_1",
            dispatch=dispatched.append,
        )

        self.assertEqual(len(dispatched), 3)
        self.assertEqual(dispatched[0]["name"], "task.logs.stream")
        self.assertEqual(dispatched[1]["payload"]["event"]["event_type"], "plan.updated")
        self.assertEqual(dispatched[2]["payload"]["event"]["event_type"], "task.completed")
