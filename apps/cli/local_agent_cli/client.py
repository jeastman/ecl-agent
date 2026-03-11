from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable

from packages.protocol.local_agent_protocol.models import JsonRpcError, JsonRpcRequest


class RuntimeClientError(RuntimeError):
    pass


RuntimeCommandFactory = Callable[[str], list[str]]


def runtime_command(config_path: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "apps.runtime.local_agent_runtime.main",
        "--config",
        config_path,
    ]


@dataclass(slots=True)
class StreamResponse:
    response: dict[str, Any]
    events: list[dict[str, Any]]


class RuntimeClient:
    def __init__(
        self,
        config_path: str,
        command_factory: RuntimeCommandFactory = runtime_command,
    ) -> None:
        self._config_path = config_path
        self._command_factory = command_factory

    def send(self, request: JsonRpcRequest) -> dict[str, Any]:
        return self.stream(request).response

    def consume_stream(
        self,
        request: JsonRpcRequest,
        on_event: Callable[[dict[str, Any]], None],
        on_response: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        process = subprocess.Popen(
            self._command_factory(self._config_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert process.stdin is not None
            process.stdin.write(json.dumps(request.to_dict()) + "\n")
            process.stdin.close()

            assert process.stdout is not None
            response_line = process.stdout.readline()
            if not response_line.strip():
                stderr = _read_stream(process.stderr)
                return_code = process.wait()
                if stderr:
                    sys.stderr.write(stderr)
                    sys.stderr.flush()
                if return_code != 0:
                    raise RuntimeClientError(
                        f"runtime exited with code {return_code}"
                        + (f": {stderr.strip()}" if stderr.strip() else "")
                    )
                raise RuntimeClientError("runtime returned no response")

            response = _parse_json_payload(response_line)
            if "error" in response and response["error"] is not None:
                error = JsonRpcError.from_dict(response["error"])
                _drain_stdout_events(process.stdout, on_event)
                stderr = _read_stream(process.stderr)
                return_code = process.wait()
                if stderr:
                    sys.stderr.write(stderr)
                    sys.stderr.flush()
                if return_code != 0:
                    raise RuntimeClientError(
                        f"runtime exited with code {return_code}"
                        + (f": {stderr.strip()}" if stderr.strip() else "")
                    )
                raise RuntimeClientError(f"{error.code} {error.message}")

            if on_response is not None:
                on_response(response)
            _drain_stdout_events(process.stdout, on_event)
            stderr = _read_stream(process.stderr)
            return_code = process.wait()
            if stderr:
                sys.stderr.write(stderr)
                sys.stderr.flush()
            if return_code != 0:
                raise RuntimeClientError(
                    f"runtime exited with code {return_code}"
                    + (f": {stderr.strip()}" if stderr.strip() else "")
                )
            return response
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def stream(self, request: JsonRpcRequest) -> StreamResponse:
        completed = subprocess.run(
            self._command_factory(self._config_path),
            input=json.dumps(request.to_dict()) + "\n",
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.stderr:
            sys.stderr.write(completed.stderr)
            sys.stderr.flush()
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise RuntimeClientError(
                f"runtime exited with code {completed.returncode}"
                + (f": {stderr}" if stderr else "")
            )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeClientError("runtime returned no response")

        payloads: list[dict[str, Any]] = []
        for line in lines:
            payloads.append(_parse_json_payload(line))

        response = payloads[0]
        if "error" in response and response["error"] is not None:
            error = JsonRpcError.from_dict(response["error"])
            raise RuntimeClientError(f"{error.code} {error.message}")

        events: list[dict[str, Any]] = []
        for payload in payloads[1:]:
            if payload.get("type") != "runtime.event":
                raise RuntimeClientError(
                    "runtime returned unexpected non-event payload after response"
                )
            events.append(payload)
        return StreamResponse(response=response, events=events)


def _parse_json_payload(line: str) -> dict[str, Any]:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise RuntimeClientError(f"runtime returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeClientError("runtime returned a non-object JSON payload")
    return payload


def _drain_stdout_events(
    stdout: Any,
    on_event: Callable[[dict[str, Any]], None],
) -> None:
    for line in stdout:
        if not line.strip():
            continue
        payload = _parse_json_payload(line)
        if payload.get("type") != "runtime.event":
            raise RuntimeClientError("runtime returned unexpected non-event payload after response")
        on_event(payload)


def _read_stream(stream: Any) -> str:
    if stream is None:
        return ""
    return stream.read()
