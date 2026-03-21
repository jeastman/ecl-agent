from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from apps.cli.local_agent_cli.client import RuntimeClient, RuntimeClientError
from apps.cli.local_agent_cli.renderers import (
    render_approval_result,
    render_approvals,
    render_artifacts,
    render_config,
    render_diagnostics,
    render_event_timeline,
    render_health,
    render_logs_stream_open,
    render_memory,
    render_skill_install,
    render_task_cancelled,
    render_task_created,
    render_task_snapshot,
)
from packages.config.local_agent_config.loader import load_runtime_config
from packages.protocol.local_agent_protocol.models import (
    ApprovalDecisionPayload,
    JsonRpcRequest,
    METHOD_CONFIG_GET,
    METHOD_MEMORY_INSPECT,
    METHOD_RUNTIME_HEALTH,
    METHOD_SKILL_INSTALL,
    METHOD_TASK_APPROVE,
    METHOD_TASK_APPROVALS_LIST,
    METHOD_TASK_DIAGNOSTICS_LIST,
    METHOD_TASK_ARTIFACTS_LIST,
    METHOD_TASK_CANCEL,
    METHOD_TASK_CREATE,
    METHOD_TASK_GET,
    METHOD_TASK_LOGS_STREAM,
    METHOD_TASK_REPLY,
    METHOD_TASK_RESUME,
    MemoryInspectParams,
    SkillInstallParams,
    TaskApprovalsListParams,
    TaskApproveParams,
    TaskDiagnosticsListParams,
    TaskArtifactsListParams,
    TaskCancelParams,
    TaskCreateParams,
    TaskCreateRequest,
    TaskGetParams,
    TaskLogsStreamParams,
    TaskReplyParams,
    TaskResumeParams,
)
from packages.task_model.local_agent_task_model.ids import new_correlation_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run and inspect Local Agent Harness tasks.",
        epilog=(
            "Examples:\n"
            '  agent run "Inspect the repository workspace"\n'
            "  agent status task_123 --run-id run_456\n"
            "  agent logs task_123 --run-id run_456\n"
            "  agent approvals task_123"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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

    cancel = subparsers.add_parser("cancel", help="Interrupt a task and checkpoint it for resume.")
    cancel.add_argument("task_id", help="Task identifier.")
    cancel.add_argument("--run-id", help="Optional run identifier.")
    cancel.add_argument("--reason", help="Optional cancellation reason.")

    logs = subparsers.add_parser("logs", help="Render runtime events for a task.")
    logs.add_argument("task_id", help="Task identifier.")
    logs.add_argument("--run-id", help="Optional run identifier.")

    artifacts = subparsers.add_parser("artifacts", help="List runtime-owned artifacts for a task.")
    artifacts.add_argument("task_id", help="Task identifier.")
    artifacts.add_argument("--run-id", help="Optional run identifier.")

    approvals = subparsers.add_parser("approvals", help="List approvals for a task.")
    approvals.add_argument("task_id", help="Task identifier.")
    approvals.add_argument("--run-id", help="Optional run identifier.")

    diagnostics = subparsers.add_parser(
        "diagnostics", help="List persisted diagnostics for a task."
    )
    diagnostics.add_argument("task_id", help="Task identifier.")
    diagnostics.add_argument("--run-id", help="Optional run identifier.")

    approve = subparsers.add_parser("approve", help="Submit an approval decision.")
    approve.add_argument("approval_id", help="Approval identifier.")
    approve.add_argument(
        "--decision",
        choices=("approve", "reject"),
        required=True,
        help="Decision to submit.",
    )
    approve.add_argument("--task-id", help="Optional task identifier.")
    approve.add_argument("--run-id", help="Optional run identifier.")

    resume = subparsers.add_parser("resume", help="Resume a paused or resumable task.")
    resume.add_argument("task_id", help="Task identifier.")
    resume.add_argument("--run-id", help="Optional run identifier.")

    reply = subparsers.add_parser(
        "reply", help="Reply to a paused task awaiting user input and continue it."
    )
    reply.add_argument("task_id", help="Task identifier.")
    reply.add_argument("--run-id", help="Optional run identifier.")
    reply.add_argument("--message", required=True, help="Reply message to send to the task.")

    memory = subparsers.add_parser("memory", help="Inspect runtime memory entries.")
    memory.add_argument("--task-id", help="Optional task identifier.")
    memory.add_argument("--run-id", help="Optional run identifier.")
    memory.add_argument(
        "--scope",
        choices=("project", "identity", "run_state", "scratch"),
        help="Optional memory scope filter.",
    )
    memory.add_argument("--namespace", help="Optional namespace filter.")

    subparsers.add_parser("config", help="Inspect redacted runtime config.")
    skill_install = subparsers.add_parser(
        "skill-install", help="Install a staged skill through the runtime."
    )
    skill_install.add_argument("task_id", help="Task identifier.")
    skill_install.add_argument("--run-id", required=True, help="Run identifier.")
    skill_install.add_argument("--source-path", required=True, help="Sandbox source path.")
    skill_install.add_argument(
        "--target-scope",
        required=True,
        choices=("primary_agent", "subagent"),
        help="Managed install scope.",
    )
    skill_install.add_argument("--target-role", help="Subagent role when target scope is subagent.")
    skill_install.add_argument(
        "--install-mode",
        choices=("fail_if_exists", "replace"),
        default="fail_if_exists",
        help="Conflict handling mode.",
    )
    skill_install.add_argument("--reason", required=True, help="Reason for installation.")
    return parser


def make_client(config_path: str) -> RuntimeClient:
    return RuntimeClient(config_path)


def make_console() -> Console:
    return Console(highlight=False, width=140)


def handle_health(config_path: str) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_RUNTIME_HEALTH,
        params={},
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    result = payload["result"]
    console.print(render_health(result, payload.get("correlation_id")))
    return 0


def handle_run(
    config_path: str,
    objective: str,
    workspace_roots: list[str],
    constraints: list[str],
    success_criteria: list[str],
) -> int:
    client = make_client(config_path)
    console = make_console()
    resolved_workspace_roots = workspace_roots or [_default_workspace_root(config_path)]
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
    console.print(render_task_created(result, payload.get("correlation_id")))
    return 0


def _default_workspace_root(config_path: str) -> str:
    config = load_runtime_config(config_path)
    return config.cli.virtual_workspace_root


def handle_status(config_path: str, task_id: str, run_id: str | None) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_TASK_GET,
        params=TaskGetParams(task_id=task_id, run_id=run_id).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    console.print(render_task_snapshot(payload["result"]["task"]))
    return 0


def handle_cancel(
    config_path: str,
    task_id: str,
    run_id: str | None,
    reason: str | None,
) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_TASK_CANCEL,
        params=TaskCancelParams(task_id=task_id, run_id=run_id, reason=reason).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    console.print(render_task_cancelled(payload["result"], payload.get("correlation_id")))
    return 0


def handle_logs(config_path: str, task_id: str, run_id: str | None) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_TASK_LOGS_STREAM,
        params=TaskLogsStreamParams(task_id=task_id, run_id=run_id, include_history=True).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    client.consume_stream(
        request,
        on_response=lambda response_payload: console.print(
            render_logs_stream_open(
                task_id=response_payload["result"]["task_id"],
                run_id=response_payload["result"]["run_id"],
                stream_open=response_payload["result"]["stream_open"],
            )
        ),
        on_event=lambda event_payload: console.print(render_event_timeline([event_payload])[0]),
    )
    return 0


def handle_artifacts(config_path: str, task_id: str, run_id: str | None) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_TASK_ARTIFACTS_LIST,
        params=TaskArtifactsListParams(task_id=task_id, run_id=run_id).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    console.print(render_artifacts(payload["result"]["artifacts"]))
    return 0


def handle_approvals(config_path: str, task_id: str, run_id: str | None) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_TASK_APPROVALS_LIST,
        params=TaskApprovalsListParams(task_id=task_id, run_id=run_id).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    console.print(render_approvals(payload["result"]["approvals"]))
    return 0


def handle_diagnostics(config_path: str, task_id: str, run_id: str | None) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_TASK_DIAGNOSTICS_LIST,
        params=TaskDiagnosticsListParams(task_id=task_id, run_id=run_id).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    console.print(render_diagnostics(payload["result"]["diagnostics"]))
    return 0


def handle_approve(
    config_path: str,
    task_id: str | None,
    approval_id: str,
    decision: str,
    run_id: str | None,
) -> int:
    client = make_client(config_path)
    console = make_console()
    normalized_decision = "approved" if decision == "approve" else "rejected"
    request = JsonRpcRequest(
        method=METHOD_TASK_APPROVE,
        params=TaskApproveParams(
            task_id=task_id,
            run_id=run_id,
            approval=ApprovalDecisionPayload(
                approval_id=approval_id,
                decision=normalized_decision,
            ),
        ).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    result = payload["result"]
    console.print(render_approval_result(result))
    console.print(render_task_snapshot(result["task"]))
    return 0


def handle_resume(config_path: str, task_id: str, run_id: str | None) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_TASK_RESUME,
        params=TaskResumeParams(task_id=task_id, run_id=run_id).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    console.print(render_task_snapshot(payload["result"]["task"], title="Task Resumed"))
    return 0


def handle_reply(
    config_path: str,
    task_id: str,
    run_id: str | None,
    message: str,
) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_TASK_REPLY,
        params=TaskReplyParams(task_id=task_id, run_id=run_id, message=message).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    console.print(render_task_snapshot(payload["result"]["task"], title="Task Reply Accepted"))
    return 0


def handle_memory(
    config_path: str,
    task_id: str | None,
    run_id: str | None,
    scope: str | None,
    namespace: str | None,
) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_MEMORY_INSPECT,
        params=MemoryInspectParams(
            task_id=task_id,
            run_id=run_id,
            scope=scope,
            namespace=namespace,
        ).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    result = payload["result"]
    console.print(render_memory(result["entries"], scope=result["scope"], count=result["count"]))
    return 0


def handle_config(config_path: str) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_CONFIG_GET,
        params={},
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    console.print(render_config(payload["result"]))
    return 0


def handle_skill_install(
    config_path: str,
    task_id: str,
    run_id: str,
    source_path: str,
    target_scope: str,
    target_role: str | None,
    install_mode: str,
    reason: str,
) -> int:
    client = make_client(config_path)
    console = make_console()
    request = JsonRpcRequest(
        method=METHOD_SKILL_INSTALL,
        params=SkillInstallParams(
            task_id=task_id,
            run_id=run_id,
            source_path=source_path,
            target_scope=target_scope,
            target_role=target_role,
            install_mode=install_mode,
            reason=reason,
        ).to_dict(),
        id="1",
        correlation_id=new_correlation_id(),
    )
    payload = client.send(request)
    console.print(render_skill_install(payload["result"]))
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
        if args.command == "cancel":
            return handle_cancel(
                config_path=config_path,
                task_id=args.task_id,
                run_id=args.run_id,
                reason=args.reason,
            )
        if args.command == "logs":
            return handle_logs(config_path=config_path, task_id=args.task_id, run_id=args.run_id)
        if args.command == "artifacts":
            return handle_artifacts(
                config_path=config_path,
                task_id=args.task_id,
                run_id=args.run_id,
            )
        if args.command == "approvals":
            return handle_approvals(
                config_path=config_path,
                task_id=args.task_id,
                run_id=args.run_id,
            )
        if args.command == "diagnostics":
            return handle_diagnostics(
                config_path=config_path,
                task_id=args.task_id,
                run_id=args.run_id,
            )
        if args.command == "approve":
            return handle_approve(
                config_path=config_path,
                task_id=args.task_id,
                approval_id=args.approval_id,
                decision=args.decision,
                run_id=args.run_id,
            )
        if args.command == "resume":
            return handle_resume(
                config_path=config_path,
                task_id=args.task_id,
                run_id=args.run_id,
            )
        if args.command == "reply":
            return handle_reply(
                config_path=config_path,
                task_id=args.task_id,
                run_id=args.run_id,
                message=args.message,
            )
        if args.command == "memory":
            return handle_memory(
                config_path=config_path,
                task_id=args.task_id,
                run_id=args.run_id,
                scope=args.scope,
                namespace=args.namespace,
            )
        if args.command == "config":
            return handle_config(config_path=config_path)
        if args.command == "skill-install":
            return handle_skill_install(
                config_path=config_path,
                task_id=args.task_id,
                run_id=args.run_id,
                source_path=args.source_path,
                target_scope=args.target_scope,
                target_role=args.target_role,
                install_mode=args.install_mode,
                reason=args.reason,
            )
    except RuntimeClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
