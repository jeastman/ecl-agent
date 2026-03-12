from __future__ import annotations

from typing import Any, Callable

from .protocol_client import ProtocolClient


Dispatch = Callable[[dict[str, Any]], object]


async def consume_task_stream(
    client: ProtocolClient,
    *,
    task_id: str,
    run_id: str | None,
    dispatch: Dispatch,
) -> None:
    response = await client.task_logs_stream(task_id, run_id, include_history=True)
    dispatch({"kind": "rpc", "name": "task.logs.stream", "payload": response})
    selected_run_id = run_id or str(response.get("result", {}).get("run_id", ""))
    while True:
        event = await client.next_event()
        envelope = event.get("event", {})
        if envelope.get("task_id") != task_id:
            continue
        envelope_run_id = str(envelope.get("run_id", ""))
        if selected_run_id and envelope_run_id != selected_run_id:
            continue
        dispatch({"kind": "event", "payload": event})
        event_type = envelope.get("event_type")
        if event_type in {"task.completed", "task.failed"}:
            return
