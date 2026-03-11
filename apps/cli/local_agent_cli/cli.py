from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from packages.protocol.local_agent_protocol.models import (
    JsonRpcError,
    JsonRpcRequest,
    METHOD_RUNTIME_HEALTH,
    METHOD_TASK_CREATE,
    TaskCreateParams,
    TaskCreateRequest,
)
from packages.task_model.local_agent_task_model.ids import new_correlation_id


class RuntimeClientError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Agent Harness CLI")
    parser.add_argument(
        "--config",
        default="docs/architecture/runtime.example.toml",
        help="Path to the runtime config file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health", help="Check runtime health.")

    submit = subparsers.add_parser("submit", help="Create a task through the runtime.")
    submit.add_argument("objective", help="Task objective.")
    submit.add_argument(
        "--workspace-root",
        action="append",
        default=[],
        help="Workspace root the runtime should associate with the task.",
    )
    submit.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="Constraint to attach to the task.",
    )
    submit.add_argument(
        "--success-criteria",
        action="append",
        default=[],
        help="Success criteria to attach to the task.",
    )
    return parser


def runtime_command(config_path: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "apps.runtime.local_agent_runtime.main",
        "--config",
        config_path,
    ]


def send_rpc(command: list[str], request: JsonRpcRequest) -> dict[str, Any]:
    completed = subprocess.run(
        command,
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
            f"runtime exited with code {completed.returncode}" + (f": {stderr}" if stderr else "")
        )

    stdout = completed.stdout.strip()
    if not stdout:
        raise RuntimeClientError("runtime returned no response")

    try:
        payload = json.loads(stdout.splitlines()[0])
    except json.JSONDecodeError as exc:
        raise RuntimeClientError(f"runtime returned invalid JSON: {exc}") from exc

    if "error" in payload and payload["error"] is not None:
        error = JsonRpcError.from_dict(payload["error"])
        raise RuntimeClientError(f"{error.code} {error.message}")

    return payload


def handle_health(config_path: str) -> int:
    request = JsonRpcRequest(
        method=METHOD_RUNTIME_HEALTH,
        params={},
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = send_rpc(runtime_command(config_path), request)
    result = payload["result"]
    print(
        f"runtime={result['runtime_name']} version={result['runtime_version']} "
        f"status={result['status']} correlation_id={result['correlation_id']}"
    )
    print(
        f"identity={result['identity']['path']} "
        f"hash={result['identity']['sha256'][:12]} transport={result['transport']} "
        f"protocol={result['protocol_version']}"
    )
    return 0


def handle_submit(
    config_path: str,
    objective: str,
    workspace_roots: list[str],
    constraints: list[str],
    success_criteria: list[str],
) -> int:
    resolved_workspace_roots = workspace_roots or [str(Path.cwd())]
    request = JsonRpcRequest(
        method=METHOD_TASK_CREATE,
        params=TaskCreateParams(
            task=TaskCreateRequest(
                objective=objective,
                workspace_roots=resolved_workspace_roots,
                constraints=constraints,
                success_criteria=success_criteria,
            )
        ).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = send_rpc(runtime_command(config_path), request)
    result = payload["result"]
    print(
        f"task_id={result['task_id']} run_id={result['run_id']} status={result['status']} "
        f"correlation_id={payload['correlation_id']}"
    )
    print(f"accepted_at={result['accepted_at']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_path = str(Path(args.config))

    try:
        if args.command == "health":
            return handle_health(config_path)
        if args.command == "submit":
            return handle_submit(
                config_path=config_path,
                objective=args.objective,
                workspace_roots=args.workspace_root,
                constraints=args.constraint,
                success_criteria=args.success_criteria,
            )
    except RuntimeClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
