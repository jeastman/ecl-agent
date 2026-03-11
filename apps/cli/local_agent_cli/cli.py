from __future__ import annotations

import argparse
import sys
from pathlib import Path

from apps.cli.local_agent_cli.client import RuntimeClient, RuntimeClientError
from apps.cli.local_agent_cli.renderers import (
    render_artifacts,
    render_event_timeline,
    render_health,
    render_task_created,
    render_task_snapshot,
)
from packages.protocol.local_agent_protocol.models import (
    JsonRpcRequest,
    METHOD_RUNTIME_HEALTH,
    METHOD_TASK_ARTIFACTS_LIST,
    METHOD_TASK_CREATE,
    METHOD_TASK_GET,
    METHOD_TASK_LOGS_STREAM,
    METHOD_TASK_RESUME,
    TaskArtifactsListParams,
    TaskCreateParams,
    TaskCreateRequest,
    TaskGetParams,
    TaskLogsStreamParams,
    TaskResumeParams,
)
from packages.task_model.local_agent_task_model.ids import new_correlation_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Agent Harness CLI")
    parser.add_argument(
        "--config",
        default="docs/architecture/runtime.example.toml",
        help="Path to the runtime config file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health", help="Check runtime health.")

    run = subparsers.add_parser(
        "run", aliases=["submit"], help="Create a task through the runtime."
    )
    run.add_argument("objective", help="Task objective.")
    run.add_argument(
        "--workspace-root",
        action="append",
        default=[],
        help="Workspace root the runtime should associate with the task.",
    )
    run.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="Constraint to attach to the task.",
    )
    run.add_argument(
        "--success-criteria",
        action="append",
        default=[],
        help="Success criteria to attach to the task.",
    )
    status = subparsers.add_parser("status", help="Inspect task state through the runtime.")
    status.add_argument("task_id", help="Task identifier.")
    status.add_argument("--run-id", help="Optional run identifier.")

    logs = subparsers.add_parser("logs", help="Render runtime events for a task.")
    logs.add_argument("task_id", help="Task identifier.")
    logs.add_argument("--run-id", help="Optional run identifier.")

    artifacts = subparsers.add_parser("artifacts", help="List runtime-owned artifacts for a task.")
    artifacts.add_argument("task_id", help="Task identifier.")
    artifacts.add_argument("--run-id", help="Optional run identifier.")

    resume = subparsers.add_parser("resume", help="Resume a paused or resumable task.")
    resume.add_argument("task_id", help="Task identifier.")
    resume.add_argument("--run-id", help="Optional run identifier.")
    return parser


def make_client(config_path: str) -> RuntimeClient:
    return RuntimeClient(config_path)


def handle_health(config_path: str) -> int:
    client = make_client(config_path)
    request = JsonRpcRequest(
        method=METHOD_RUNTIME_HEALTH,
        params={},
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    result = payload["result"]
    for line in render_health(result, payload.get("correlation_id")):
        print(line)
    return 0


def handle_run(
    config_path: str,
    objective: str,
    workspace_roots: list[str],
    constraints: list[str],
    success_criteria: list[str],
) -> int:
    client = make_client(config_path)
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
    payload = client.send(request)
    result = payload["result"]
    for line in render_task_created(result, payload.get("correlation_id")):
        print(line)
    return 0


def handle_status(config_path: str, task_id: str, run_id: str | None) -> int:
    client = make_client(config_path)
    request = JsonRpcRequest(
        method=METHOD_TASK_GET,
        params=TaskGetParams(task_id=task_id, run_id=run_id).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    for line in render_task_snapshot(payload["result"]["task"]):
        print(line)
    return 0


def handle_logs(config_path: str, task_id: str, run_id: str | None) -> int:
    client = make_client(config_path)
    request = JsonRpcRequest(
        method=METHOD_TASK_LOGS_STREAM,
        params=TaskLogsStreamParams(task_id=task_id, run_id=run_id, include_history=True).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    client.consume_stream(
        request,
        on_response=lambda response_payload: print(
            "task_id="
            f"{response_payload['result']['task_id']} "
            f"run_id={response_payload['result']['run_id']} "
            f"stream_open={response_payload['result']['stream_open']}"
        ),
        on_event=lambda event_payload: print(render_event_timeline([event_payload])[0]),
    )
    return 0


def handle_artifacts(config_path: str, task_id: str, run_id: str | None) -> int:
    client = make_client(config_path)
    request = JsonRpcRequest(
        method=METHOD_TASK_ARTIFACTS_LIST,
        params=TaskArtifactsListParams(task_id=task_id, run_id=run_id).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    for line in render_artifacts(payload["result"]["artifacts"]):
        print(line)
    return 0


def handle_resume(config_path: str, task_id: str, run_id: str | None) -> int:
    client = make_client(config_path)
    request = JsonRpcRequest(
        method=METHOD_TASK_RESUME,
        params=TaskResumeParams(task_id=task_id, run_id=run_id).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    for line in render_task_snapshot(payload["result"]["task"]):
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_path = str(Path(args.config))

    try:
        if args.command == "health":
            return handle_health(config_path)
        if args.command in {"run", "submit"}:
            return handle_run(
                config_path=config_path,
                objective=args.objective,
                workspace_roots=args.workspace_root,
                constraints=args.constraint,
                success_criteria=args.success_criteria,
            )
        if args.command == "status":
            return handle_status(config_path=config_path, task_id=args.task_id, run_id=args.run_id)
        if args.command == "logs":
            return handle_logs(config_path=config_path, task_id=args.task_id, run_id=args.run_id)
        if args.command == "artifacts":
            return handle_artifacts(
                config_path=config_path,
                task_id=args.task_id,
                run_id=args.run_id,
            )
        if args.command == "resume":
            return handle_resume(
                config_path=config_path,
                task_id=args.task_id,
                run_id=args.run_id,
            )
    except RuntimeClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
