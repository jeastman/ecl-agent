# Local Agent Harness

Local Agent Harness is a local-first agent runtime built as a Python monorepo. The runtime is the system of record for execution, and the repository currently ships two clients over that runtime-owned protocol:

- a thin CLI for submitting and inspecting work
- a Textual TUI for operator workflows such as task browsing, event review, approvals, artifact preview, memory inspection, and config inspection

The current implemented baseline is Milestone 3:

- JSON-RPC 2.0 over stdio between clients and the runtime
- runtime-owned task lifecycle, artifacts, approvals, checkpoints, diagnostics, and memory
- a real DeepAgent-backed primary harness behind project-owned adapters
- governed sandbox access for files and commands
- durable restart recovery and pause/resume
- filesystem-backed subagent registry, role-scoped tools, and model routing
- governed skill installation into managed primary-agent and subagent skill roots

## Architecture

The repository follows a few non-negotiable rules:

- the runtime owns task lifecycle and execution state
- clients stay thin and do not implement orchestration logic
- DeepAgent and LangChain types stay inside the adapter layer
- filesystem and command side effects go through the sandbox interface
- shared protocol, config, and task contracts live in common packages
- checkpoint state stays separate from durable project memory

The implemented execution flow is:

1. A client calls `task.create`.
2. The runtime creates task and run state.
3. The runtime starts execution and invokes the primary harness.
4. The harness uses runtime-governed tools to inspect the workspace, delegate to subagents, and write outputs.
5. Runtime policy allows, denies, or pauses on approval boundaries.
6. Events, checkpoints, diagnostics, metrics, and artifacts persist during execution.
7. Paused runs continue through `task.resume`, `task.reply`, or `task.approve`.
8. Clients read runtime-owned state through protocol methods instead of reconstructing it locally.

## Repository Layout

- `apps/cli` thin CLI client, runtime process wrapper, and rich renderers
- `apps/runtime` runtime bootstrap, method handlers, task runner, and stdio server
- `apps/tui` Textual operator console over the same runtime protocol
- `packages/protocol` shared JSON-RPC and runtime contract models
- `packages/config` shared runtime configuration models and loader
- `packages/identity` `IDENTITY.md` loading and identity bundle compilation
- `packages/task_model` runtime-facing task and snapshot domain models
- `packages/observability` shared logging support
- `services/deepagent_runtime` project-owned DeepAgent adapter and tool bindings
- `services/sandbox_service` governed workspace, scratch, memory, and command execution
- `services/subagent_registry` filesystem-backed subagent asset discovery
- `services/subagent_runtime` model routing, tool scopes, skills, and skill installation
- `services/checkpoint_service` checkpoint metadata and thread binding persistence
- `services/memory_service` durable memory storage and promotion
- `services/policy_service` approval and boundary policy engine
- `services/observability_service` durable event, diagnostics, and metrics stores
- `docs/specs` architecture and protocol specifications
- `docs/adr` architectural decision records

## Implemented Scope

Included today:

- runtime methods for health, task creation/list/get, logs, artifacts, approvals, diagnostics, resume, reply, memory inspection, config inspection, and skill installation
- event history replay and live event streaming
- local governed sandbox with workspace, scratch, and memory zones
- runtime-owned artifact registration and artifact preview support
- single primary-agent execution with delegated subagent support
- durable checkpoints, recovery, approval persistence, diagnostics, and run metrics
- runtime-owned model resolution for the primary agent and subagents
- CLI commands for health, run, status, logs, artifacts, approvals, diagnostics, approve, resume, reply, memory, config, and skill installation
- TUI screens for dashboard, task detail, approvals, artifacts, memory, diagnostics, config, markdown preview, and timeline filtering/search

Still deferred:

- web client
- `task.cancel`
- richer memory retrieval and governance semantics

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
- `uv run poe lint` runs Ruff checks across the repo
- `uv run poe format` formats Python sources with Ruff
- `uv run poe typecheck` runs mypy over `apps`, `packages`, and `tests`
- `uv run poe health` runs the CLI health check against the local runtime
- `uv run poe run` submits the default reference task through the CLI

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
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml run "Inspect the repository workspace"
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml status <task_id>
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml logs <task_id>
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml reply <task_id> --message "Continue with the updated requirement"
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml config
```

Run the Textual TUI:

```bash
python -m apps.tui.local_agent_tui.bootstrap --config docs/architecture/runtime.example.toml
```

## Configuration File

The runtime configuration file passed with `--config` is TOML. The example file is [docs/architecture/runtime.example.toml](/Users/jeastman/Projects/e/ecl-agent/docs/architecture/runtime.example.toml).

Relative paths in the config are resolved relative to the config file location, not the current shell directory. That applies to `identity.path` and `cli.default_workspace_root`.

Current format:

```toml
[runtime]
name = "local-agent-harness"
log_level = "info"

[transport]
mode = "stdio-jsonrpc"

[identity]
path = "../../agents/primary-agent/IDENTITY.md"

[models.default]
provider = "openai"
model = "gpt-5-nano"

[models.primary]
provider = "openai"
model = "gpt-5"

[models.subagents.researcher]
provider = "openai"
model = "gpt-5-mini"

[persistence]
root_path = "~/.local-agent-harness"
metadata_backend = "sqlite"
event_backend = "sqlite"
diagnostic_backend = "sqlite"

[cli]
default_workspace_root = "../.."

[policy]
approval_mode = "boundary"
sandbox_mode = "governed"
safe_command_classes = ["safe_read", "safe_exec"]
deny_command_classes = ["network", "destructive", "secrets"]
```

Settings:

- `runtime.name`: required runtime identifier used in health output.
- `runtime.log_level`: optional runtime log level. Defaults to `info`.
- `transport.mode`: required transport selector. The current implementation expects `stdio-jsonrpc`.
- `identity.path`: required path to the primary agent `IDENTITY.md`.
- `models.primary`: required provider and model for the primary harness.
- `models.default`: optional fallback model profile.
- `models.subagents.<role>`: optional provider/model override for a subagent role.
- `persistence.root_path`: runtime data root. The runtime stores durable metadata, scratch data, and memory under this directory.
- `persistence.metadata_backend`: currently only `sqlite` is supported.
- `persistence.event_backend`: currently only `sqlite` is supported.
- `persistence.diagnostic_backend`: currently only `sqlite` is supported.
- `cli.default_workspace_root`: default workspace root for client-submitted runs and the governed workspace boundary.
- `policy`: open-ended runtime policy table preserved and exposed through `config.get` with redaction for secret-like values.

Notes:

- If `models.default` is omitted, the primary model acts as the default fallback.
- Agent-facing filesystem tools use a virtual filesystem rooted at `/`.
- The governed workspace is mounted at `/`, scratch space at `/tmp`, and runtime memory-backed files at `/.memory`.
- Host filesystem paths such as `/Users/...` are not exposed directly to the agent.

## CLI Surface

The current CLI commands are:

- `agent health`
- `agent run "<objective>" [--workspace-root <path>]... [--constraint <text>]... [--success-criteria <text>]...`
- `agent status <task_id> [--run-id <run_id>]`
- `agent logs <task_id> [--run-id <run_id>]`
- `agent artifacts <task_id> [--run-id <run_id>]`
- `agent approvals <task_id> [--run-id <run_id>]`
- `agent diagnostics <task_id> [--run-id <run_id>]`
- `agent approve <approval_id> --decision approve|reject [--task-id <task_id>] [--run-id <run_id>]`
- `agent resume <task_id> [--run-id <run_id>]`
- `agent reply <task_id> [--run-id <run_id>] --message "<reply>"`
- `agent memory [--task-id <task_id>] [--run-id <run_id>] [--scope <scope>] [--namespace <namespace>]`
- `agent config`
- `agent skill-install <task_id> --run-id <run_id> --source-path <sandbox_path> --target-scope primary_agent|subagent [--target-role <role>] [--install-mode fail_if_exists|replace] --reason "<why>"`

`submit` remains as a compatibility alias for `run`.

## Protocol and Events

The transport is JSON-RPC 2.0 over stdio. The runtime currently implements:

- `runtime.health`
- `task.create`
- `task.list`
- `task.get`
- `task.approve`
- `task.approvals.list`
- `task.diagnostics.list`
- `task.reply`
- `task.resume`
- `task.logs.stream`
- `task.artifacts.list`
- `task.artifact.get`
- `memory.inspect`
- `skill.install`
- `config.get`

Observed event types include:

- `task.created`
- `task.started`
- `checkpoint.saved`
- `task.paused`
- `task.user_input_received`
- `task.resumed`
- `approval.requested`
- `policy.denied`
- `recovery.discovered`
- `plan.updated`
- `subagent.started`
- `subagent.completed`
- `tool.called`
- `artifact.created`
- `skill.install.requested`
- `skill.install.validated`
- `skill.install.approval_requested`
- `skill.install.completed`
- `skill.install.failed`
- `task.completed`
- `task.failed`

## Documentation Map

- [Current implementation status](/Users/jeastman/Projects/e/ecl-agent/docs/current.status.md)
- [Master architecture spec](/Users/jeastman/Projects/e/ecl-agent/docs/specs/local-agent-harness-master-spec-v1.md)
- [Runtime protocol spec](/Users/jeastman/Projects/e/ecl-agent/docs/specs/local-agent-harness-runtime-protocol-spec-v1.md)
- [Architecture notes](/Users/jeastman/Projects/e/ecl-agent/docs/architecture/README.md)
- [ADR index](/Users/jeastman/Projects/e/ecl-agent/docs/adr/README.md)
- [CLI README](/Users/jeastman/Projects/e/ecl-agent/apps/cli/README.md)
- [Runtime README](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/README.md)
- [Apps overview](/Users/jeastman/Projects/e/ecl-agent/apps/README.md)

## Status

The repository is past the earlier Milestone 2 baseline. The current codebase implements the durable runtime-governance features from Milestone 2 plus the Milestone 3 subagent, routing, and governed skill-installation baseline. A local operator TUI also exists today, while the web client remains future work.
