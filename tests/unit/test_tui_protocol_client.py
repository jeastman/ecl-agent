from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock

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
        client._request = AsyncMock(return_value={"result": {"tasks": []}})  # type: ignore[method-assign]
        payload = await client.task_list(limit=5)
        self.assertEqual(payload["result"]["tasks"], [])
        client._request.assert_awaited_once_with("task.list", {"limit": 5})  # type: ignore[attr-defined]
