# Local Agent Harness

Local Agent Harness is a local-first agent runtime and CLI built as a monorepo. The project is organized around a strict separation between an authoritative runtime, thin clients, and shared contracts so agent execution can evolve without pushing orchestration logic into the user interface.

Milestone 2 is now the implemented baseline:

- CLI submits and inspects work through JSON-RPC over stdio
- runtime creates `task_id` and `run_id` and owns execution state
- runtime invokes a real DeepAgent-backed `AgentHarness`
- sandbox and runtime policy govern file, command, and memory operations
- checkpoint metadata and persisted events support pause/resume and restart recovery
- approval workflow is durable, sparse, and boundary-based
- durable memory, diagnostics, and redacted config inspection are available through runtime-owned methods
- CLI remains a thin client for status, logs, artifacts, approvals, diagnostics, resume, memory, and config inspection

The current reference task is generating a Markdown architecture summary artifact at logical path `artifacts/repo_summary.md`.

## Architecture

The repository follows a few non-negotiable rules:

- the runtime is the system of record for task lifecycle and execution state
- the CLI is a client, not the orchestration layer
- LangChain and DeepAgent types stay inside the adapter layer
- filesystem and command side effects go through the sandbox interface
- shared protocol and task contracts live in common packages, not app-local copies
- checkpoint state stays separate from durable project memory

The implemented Milestone 2 execution flow is:

1. CLI calls `task.create`
2. runtime creates task and run state
3. runtime starts the task and invokes the agent harness
4. harness uses sandbox-backed tools to inspect the workspace and write outputs
5. runtime policy allows, denies, or pauses on approval boundaries
6. checkpoint metadata, events, diagnostics, and metrics persist during execution
7. paused or approval-blocked runs resume through `task.resume` or `task.approve`
8. restart recovery reconstructs resumable run metadata from persisted state
9. CLI reads runtime-owned methods for task state, logs, artifacts, approvals, diagnostics, memory, and config

## Repository Layout

- `apps/cli` thin CLI client, JSON-RPC transport wrapper, and output renderers
- `apps/runtime` runtime bootstrap, method handlers, task runner, and stdio server
- `packages/protocol` shared JSON-RPC, task, artifact, and event envelope models
- `packages/identity` `IDENTITY.md` loading and identity bundle compilation
- `packages/task_model` runtime-facing task and snapshot domain models
- `packages/config` runtime configuration models
- `packages/observability` shared observability support types
- `services/deepagent_runtime` project-owned DeepAgent adapter and tool bindings
- `services/sandbox_service` governed workspace, scratch, memory, and command execution services
- `services/artifact_service` runtime-owned artifact registration and lookup
- `docs/specs` master architecture and runtime protocol specifications
- `docs/adr` architectural decision records for runtime/client separation, adapter boundaries, memory, sandboxing, and routing
- `docs/plans` milestone and phase plans

## Milestone 2 Scope

Included:

- protocol-backed runtime methods: `runtime.health`, `task.create`, `task.get`, `task.logs.stream`, `task.artifacts.list`, `task.approve`, `task.approvals.list`, `task.diagnostics.list`, `task.resume`, `memory.inspect`, `config.get`
- event streaming and persisted history replay
- local sandbox with workspace, scratch, and memory zones
- runtime-owned artifact registration
- single-agent DeepAgent-backed execution through a project-owned adapter
- durable checkpoint metadata, thread binding, and restart recovery
- runtime-owned policy decisions, approval persistence, and boundary grant reuse
- durable memory storage and inspection across scopes
- persisted diagnostics and run metrics
- CLI commands for health, run, status, logs, artifacts, approvals, diagnostics, approve, resume, memory, and config

Deferred to later milestones:

- multi-subagent orchestration
- remote sandbox support
- web UI

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)

Install dependencies:

```bash
uv sync --all-groups
```

## Common Commands

Root tasks are managed with `poethepoet` through `uv run poe ...`.

```bash
uv run poe sync
uv run poe test
uv run poe lint
uv run poe format
uv run poe typecheck
uv run poe health
uv run poe run
```

What they do:

- `uv run poe sync` installs or updates the local environment
- `uv run poe test` runs the repository test suite
- `uv run poe lint` runs Ruff checks
- `uv run poe format` formats Python sources with Ruff
- `uv run poe typecheck` runs mypy over `apps`, `packages`, and `tests`
- `uv run poe health` runs the CLI health check against the local runtime
- `uv run poe run` submits the default Milestone 2 reference task through the CLI

## Quick Start

Check that the runtime can boot through the CLI:

```bash
uv run poe health
```

Submit the default reference task:

```bash
uv run poe run
```

Run the CLI directly with the example config:

```bash
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml health
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml run "Generate a Markdown architecture summary for the repository"
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml status <task_id>
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml logs <task_id>
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml artifacts <task_id>
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml approvals <task_id>
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml diagnostics <task_id>
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml memory --scope project
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml config
```

Milestone 2 CLI surface:

- `agent health`
- `agent run "<objective>"`
- `agent status <task_id> [--run-id <run_id>]`
- `agent logs <task_id> [--run-id <run_id>]`
- `agent artifacts <task_id> [--run-id <run_id>]`
- `agent approvals <task_id> [--run-id <run_id>]`
- `agent diagnostics <task_id> [--run-id <run_id>]`
- `agent approve <approval_id> --decision approve|reject [--task-id <task_id>] [--run-id <run_id>]`
- `agent resume <task_id> [--run-id <run_id>]`
- `agent memory [--task-id <task_id>] [--run-id <run_id>] [--scope <scope>] [--namespace <namespace>]`
- `agent config`

The current root task `submit` remains as a compatibility alias for `run`, but Milestone 2 documentation and workflows should use `run`.

## Protocol and Events

The initial transport is JSON-RPC 2.0 over stdio. Request/response methods and runtime events share the same underlying stream but remain distinct at the protocol layer.

Milestone 2 runtime methods:

- `runtime.health`
- `task.create`
- `task.get`
- `task.approve`
- `task.approvals.list`
- `task.diagnostics.list`
- `task.resume`
- `task.logs.stream`
- `task.artifacts.list`
- `memory.inspect`
- `config.get`

Milestone 2 event types:

- `task.created`
- `task.started`
- `checkpoint.saved`
- `task.paused`
- `task.resumed`
- `approval.requested`
- `policy.denied`
- `recovery.discovered`
- `plan.updated`
- `subagent.started`
- `tool.called`
- `artifact.created`
- `task.completed`
- `task.failed`

## Documentation Map

- [Master architecture spec](docs/specs/local-agent-harness-master-spec-v1.md)
- [Runtime protocol spec](docs/specs/local-agent-harness-runtime-protocol-spec-v1.md)
- [Architecture notes](docs/architecture/README.md)
- [ADR index](docs/adr/README.md)
- [Milestone 2 specification](docs/plans/MILESTONE-2.md)
- [Milestone 2 implementation blueprint](docs/plans/MILESTONE-2-implementation-blueprint.md)
- [Milestone 2 Phase 6 closure plan](docs/plans/milestone-2.phase-6.md)
- [CLI README](apps/cli/README.md)
- [Runtime README](apps/runtime/README.md)

## Status

The repository is in the Milestone 2 closure state. It provides a durable, resumable, governed, and inspectable single-agent runtime baseline while leaving Milestone 3 items such as sub-agent orchestration, role-based routing, and web clients explicitly deferred.
