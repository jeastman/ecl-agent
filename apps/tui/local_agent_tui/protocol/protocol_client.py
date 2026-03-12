from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from packages.protocol.local_agent_protocol.models import (
    METHOD_CONFIG_GET,
    JsonRpcRequest,
    METHOD_MEMORY_INSPECT,
    METHOD_RUNTIME_HEALTH,
    METHOD_TASK_APPROVE,
    METHOD_TASK_APPROVALS_LIST,
    METHOD_TASK_ARTIFACT_GET,
    METHOD_TASK_ARTIFACTS_LIST,
    METHOD_TASK_GET,
    METHOD_TASK_LIST,
    METHOD_TASK_LOGS_STREAM,
    METHOD_TASK_RESUME,
    MemoryInspectParams,
    TaskApprovalsListParams,
    TaskArtifactGetParams,
    TaskApproveParams,
    TaskArtifactsListParams,
    TaskGetParams,
    TaskListParams,
    TaskLogsStreamParams,
    TaskResumeParams,
    ApprovalDecisionPayload,
)


class ProtocolClientError(RuntimeError):
    pass


class ProtocolClient:
    def __init__(self, config_path: str) -> None:
        self._config_path = config_path
        self._process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._request_lock = asyncio.Lock()
        self._next_request_id = 1
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def connect(self) -> None:
        if self._process is not None:
            return
        self._process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "apps.runtime.local_agent_runtime.main",
            "--config",
            self._config_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._read_stdout())

    async def close(self) -> None:
        if self._process is None:
            return
        if self._process.stdin is not None:
            self._process.stdin.close()
            await self._process.stdin.wait_closed()
        if self._reader_task is not None:
            await self._reader_task
        await self._process.wait()
        self._process = None
        self._reader_task = None

    async def runtime_health(self) -> dict[str, Any]:
        return await self._request(METHOD_RUNTIME_HEALTH, {})

    async def memory_inspect(
        self,
        *,
        task_id: str | None = None,
        run_id: str | None = None,
        scope: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            METHOD_MEMORY_INSPECT,
            MemoryInspectParams(
                task_id=task_id,
                run_id=run_id,
                scope=scope,
                namespace=namespace,
            ).to_dict(),
        )

    async def get_config(self) -> dict[str, Any]:
        return await self._request(METHOD_CONFIG_GET, {})

    async def task_get(self, task_id: str, run_id: str | None = None) -> dict[str, Any]:
        return await self._request(
            METHOD_TASK_GET,
            TaskGetParams(task_id=task_id, run_id=run_id).to_dict(),
        )

    async def task_list(self, *, limit: int | None = None) -> dict[str, Any]:
        return await self._request(
            METHOD_TASK_LIST,
            TaskListParams(limit=limit).to_dict(),
        )

    async def task_approvals_list(self, task_id: str, run_id: str | None = None) -> dict[str, Any]:
        return await self._request(
            METHOD_TASK_APPROVALS_LIST,
            TaskApprovalsListParams(task_id=task_id, run_id=run_id).to_dict(),
        )

    async def task_approve(
        self,
        task_id: str | None,
        run_id: str | None,
        approval_id: str,
        decision: str,
    ) -> dict[str, Any]:
        return await self._request(
            METHOD_TASK_APPROVE,
            TaskApproveParams(
                task_id=task_id,
                run_id=run_id,
                approval=ApprovalDecisionPayload(
                    approval_id=approval_id,
                    decision=decision,
                ),
            ).to_dict(),
        )

    async def task_artifacts_list(self, task_id: str, run_id: str | None = None) -> dict[str, Any]:
        return await self._request(
            METHOD_TASK_ARTIFACTS_LIST,
            TaskArtifactsListParams(task_id=task_id, run_id=run_id).to_dict(),
        )

    async def task_artifact_get(
        self,
        task_id: str,
        artifact_id: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            METHOD_TASK_ARTIFACT_GET,
            TaskArtifactGetParams(
                task_id=task_id,
                artifact_id=artifact_id,
                run_id=run_id,
            ).to_dict(),
        )

    async def task_logs_stream(
        self,
        task_id: str,
        run_id: str | None = None,
        *,
        include_history: bool,
    ) -> dict[str, Any]:
        return await self._request(
            METHOD_TASK_LOGS_STREAM,
            TaskLogsStreamParams(
                task_id=task_id,
                run_id=run_id,
                include_history=include_history,
            ).to_dict(),
        )

    async def task_resume(self, task_id: str, run_id: str | None = None) -> dict[str, Any]:
        return await self._request(
            METHOD_TASK_RESUME,
            TaskResumeParams(task_id=task_id, run_id=run_id).to_dict(),
        )

    async def next_event(self) -> dict[str, Any]:
        return await self._events.get()

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        await self.connect()
        assert self._process is not None
        assert self._process.stdin is not None

        async with self._request_lock:
            request_id = str(self._next_request_id)
            self._next_request_id += 1
            loop = asyncio.get_running_loop()
            future: asyncio.Future[dict[str, Any]] = loop.create_future()
            self._pending[request_id] = future
            request = JsonRpcRequest(method=method, params=params, id=request_id)
            self._process.stdin.write((json.dumps(request.to_dict()) + "\n").encode("utf-8"))
            await self._process.stdin.drain()
        return await future

    async def _read_stdout(self) -> None:
        assert self._process is not None
        assert self._process.stdout is not None
        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            payload = self._parse_payload(line.decode("utf-8"))
            self._route_payload(payload)
        error = await self._read_stderr()
        for future in self._pending.values():
            if not future.done():
                future.set_exception(
                    ProtocolClientError(error or "runtime connection closed unexpectedly")
                )
        self._pending.clear()

    def _route_payload(self, payload: dict[str, Any]) -> None:
        if payload.get("type") == "runtime.event":
            self._events.put_nowait(payload)
            return
        request_id = str(payload.get("id"))
        future = self._pending.pop(request_id, None)
        if future is None:
            return
        if payload.get("error") is not None:
            future.set_exception(ProtocolClientError(str(payload["error"])))
            return
        future.set_result(payload)

    async def _read_stderr(self) -> str:
        assert self._process is not None
        assert self._process.stderr is not None
        data = await self._process.stderr.read()
        return data.decode("utf-8").strip()

    def _parse_payload(self, raw_line: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ProtocolClientError(f"runtime returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ProtocolClientError("runtime returned non-object JSON payload")
        return payload
