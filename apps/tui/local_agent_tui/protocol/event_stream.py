from __future__ import annotations

from typing import Callable

from ..store.app_state import EventMessage, RpcMessage
from .protocol_client import ProtocolClient


Dispatch = Callable[[RpcMessage | EventMessage], object]


async def consume_task_stream(
    client: ProtocolClient,
    *,
    task_id: str,
    run_id: str | None,
    dispatch: Dispatch,
) -> None:
    response = await client.task_logs_stream(task_id, run_id, include_history=True)
    dispatch({"kind": "rpc", "name": "task.logs.stream", "payload": response})
    while True:
        event = await client.next_event()
        dispatch({"kind": "event", "payload": event})
        event_type = event.get("event", {}).get("event_type")
        if event_type in {"task.completed", "task.failed"}:
            return
