# Local Agent Harness

Local Agent Harness is a local-first agent runtime and CLI built as a monorepo. The project is organized around a strict separation between an authoritative runtime, thin clients, and shared contracts so agent execution can evolve without pushing orchestration logic into the user interface.

Milestone 1 delivers a single-agent runtime vertical slice:

- CLI submits a task through JSON-RPC over stdio
- runtime creates `task_id` and `run_id`
- runtime invokes a real DeepAgent-backed `AgentHarness`
- sandbox mediates file and command access
- runtime emits progress events
- runtime registers artifacts
- CLI can inspect task state, logs, and artifacts

The current reference task is generating a Markdown architecture summary artifact at logical path `artifacts/repo_summary.md`.

## Architecture

The repository follows a few non-negotiable rules:

- the runtime is the system of record for task lifecycle and execution state
- the CLI is a client, not the orchestration layer
- LangChain and DeepAgent types stay inside the adapter layer
- filesystem and command side effects go through the sandbox interface
- shared protocol and task contracts live in common packages, not app-local copies

The Milestone 1 execution flow is:

1. CLI calls `task.create`
2. runtime creates task and run state
3. runtime starts the task and invokes the agent harness
4. harness uses sandbox-backed tools to inspect the workspace and write outputs
5. runtime emits `runtime.event` envelopes during execution
6. runtime registers artifacts and updates task state
7. CLI reads `task.get`, `task.logs.stream`, and `task.artifacts.list`

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

## Milestone 1 Scope

Included:

- protocol-backed runtime methods: `runtime.health`, `task.create`, `task.get`, `task.logs.stream`, `task.artifacts.list`
- event streaming and history replay
- local sandbox with workspace, scratch, and memory zones
- runtime-owned artifact registration
- single-agent DeepAgent-backed execution through a project-owned adapter
- run-local state for summaries, phase tracking, and task inspection
- CLI commands for health, run, status, logs, and artifacts

Deferred to later milestones:

- durable project memory
- approval workflows
- multi-subagent orchestration
- remote sandbox support
- resumable runs across runtime restarts
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
- `uv run poe run` submits the default Milestone 1 reference task through the CLI

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
```

Milestone 1 CLI surface:

- `agent health`
- `agent run "<objective>"`
- `agent status <task_id> [--run-id <run_id>]`
- `agent logs <task_id> [--run-id <run_id>]`
- `agent artifacts <task_id> [--run-id <run_id>]`

The current root task `submit` remains as a compatibility alias for `run`, but Milestone 1 documentation and workflows should use `run`.

## Protocol and Events

The initial transport is JSON-RPC 2.0 over stdio. Request/response methods and runtime events share the same underlying stream but remain distinct at the protocol layer.

Milestone 1 runtime methods:

- `runtime.health`
- `task.create`
- `task.get`
- `task.logs.stream`
- `task.artifacts.list`

Milestone 1 event types:

- `task.created`
- `task.started`
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
- [Milestone 1 specification](docs/plans/MILESTONE-1.md)
- [Milestone 1 implementation blueprint](docs/plans/MILESTONE-1-implementation-blueprint.md)
- [CLI README](apps/cli/README.md)
- [Runtime README](apps/runtime/README.md)

## Status

The repository is in the Milestone 1 vertical-slice stage. It is intended to prove the runtime/client architecture, adapter containment, sandbox mediation, event streaming, and artifact flow end to end before later milestones add durable memory, approvals, resumability, and broader observability.
