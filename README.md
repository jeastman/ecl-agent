# Local Agent Harness

Local Agent Harness is a local-first agent runtime built as a Python monorepo. The runtime is the system of record for execution, and the repository currently ships two clients over that runtime-owned protocol:

- a thin CLI for submitting and inspecting work
- a Textual TUI for operator workflows such as task browsing, event review, approvals, artifact preview, memory inspection, config inspection, and guided remote MCP authorization

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
- TUI screens for dashboard, task detail, approvals, artifacts, memory, diagnostics, config, markdown preview, timeline filtering/search, and remote MCP auth prompts

Still deferred:

- web client
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

The TUI now includes a first-class remote MCP auth workflow for OAuth-backed MCP servers:

- it prompts for a `runtime_user_id` when a run needs per-user remote MCP auth
- it persists that operator identity in `~/.local-agent-harness/tui-settings.json`
- it surfaces `remote_mcp_authorization_required` pauses in task detail
- it can start authorization, display or copy the authorization URL, accept pasted `code` and `state_token`, and revoke an existing grant

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

[mcp]
tool_name_prefix = true

[mcp.oauth_providers.example]
authorization_url = "https://example.com/oauth/authorize"
token_url = "https://example.com/oauth/token"
client_id = "${EXAMPLE_CLIENT_ID}"
client_secret = "${EXAMPLE_CLIENT_SECRET}"
redirect_uri = "http://localhost:4315/oauth/example/callback"
scopes = ["read", "write"]

[mcp.servers.fixture_stdio]
enabled = false
description = "Example local stdio MCP server."
command = "python3"
args = ["tests/fixtures/mcp_echo_server.py"]

[mcp.servers.fixture_remote]
enabled = false
description = "Example remote MCP server."
transport = "http"
url = "https://example.com/mcp"

[mcp.servers.fixture_remote_oauth]
enabled = false
description = "Example remote MCP server with per-user OAuth."
transport = "streamable_http"
url = "https://example.com/oauth-mcp"
auth = { mode = "oauth_user_grant", provider = "example" }
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
- `cli.virtual_workspace_root`: virtual mount point exposed to the agent. Defaults to `/workspace`.
- `policy`: open-ended runtime policy table preserved and exposed through `config.get` with redaction for secret-like values.
- `mcp.tool_name_prefix`: when `true`, MCP tools are exposed as `<server>_<tool>` to avoid collisions. Defaults to `true`.
- `mcp.oauth_providers.<provider>`: generic OAuth provider definitions for per-user remote MCP auth. Providers support `authorization_url` or `discovery_url`, `token_url` or `discovery_url`, `client_id`, `client_secret`, `redirect_uri`, optional `scopes`, and optional `audience` / `resource`.
- `mcp.servers.<name>`: native MCP server definitions. Each server supports:
  - stdio servers: `command`, optional `args`, optional `env`, optional `env_from_host`
  - remote servers: `transport` or `type` plus `url`, optional `headers`, optional `auth`
  - shared fields: `enabled`, optional `description`
- `mcp.servers.<name>.auth`: optional remote auth config. Supported modes are `static_headers` and `oauth_user_grant`.

Notes:

- If `models.default` is omitted, the primary model acts as the default fallback.
- Agent-facing filesystem tools use a virtual filesystem rooted at `/`.
- The governed workspace is mounted at `/workspace` by default, scratch space at `/tmp`, and runtime memory-backed files at `/.memory`.
- Host filesystem paths such as `/Users/...` are not exposed directly to the agent.
- Project MCP compatibility files are imported automatically from:
  - `<project>/.deepagents/.mcp.json`
  - `<project>/.mcp.json`
- Merge precedence is:
  1. `.deepagents/.mcp.json`
  2. `.mcp.json`
  3. native runtime TOML under `[mcp]`
- User-level `~/.deepagents/.mcp.json` is intentionally not imported by this runtime.

## MCP Configuration

The runtime can load MCP tools through LangChain MCP adapters and expose them to the primary agent and selected subagents. This repository currently supports MCP tools only. MCP prompts and resources are not wired into the runtime.

### What MCP support does

- loads MCP server definitions from runtime TOML and compatible project `.mcp.json` files
- exposes all enabled MCP tools to the primary agent
- exposes MCP tools to a subagent only when that role declares `mcp_tools` in its manifest
- emits runtime `tool.called` events for MCP tool invocations with server metadata
- governs MCP server startup and remote access through the same runtime approval boundary system
- supports generic per-user OAuth for remote MCP servers through configured OAuth providers and runtime-managed grants

### Native runtime TOML format

Define MCP servers in the runtime config under `[mcp]`.

Example stdio server:

```toml
[mcp]
tool_name_prefix = true

[mcp.servers.docs]
enabled = true
description = "Local MCP docs helper"
command = "python3"
args = ["scripts/my_docs_mcp.py"]
env = { DOCS_MODE = "local", DOCS_TOKEN = "${DOCS_TOKEN}" }
env_from_host = ["DOCS_TOKEN"]
```

Example remote HTTP server:

```toml
[mcp.servers.github]
enabled = true
description = "Remote GitHub MCP endpoint"
transport = "http"
url = "https://example.com/mcp"
headers = { Authorization = "Bearer ${GITHUB_TOKEN}" }
```

Example remote OAuth-backed server:

```toml
[mcp.oauth_providers.slack]
authorization_url = "https://slack.com/oauth/v2/authorize"
token_url = "https://slack.com/api/oauth.v2.access"
client_id = "${SLACK_CLIENT_ID}"
client_secret = "${SLACK_CLIENT_SECRET}"
redirect_uri = "http://localhost:4315/oauth/slack/callback"
scopes = ["channels:history", "channels:read", "chat:write", "users:read"]

[mcp.servers.slack]
enabled = true
description = "Slack MCP"
transport = "streamable_http"
url = "https://mcp.slack.com/mcp"
auth = { mode = "oauth_user_grant", provider = "slack" }
```

Rules:

- A server must define either `command` or `url`, never both.
- `command` implies `stdio` transport.
- `url` requires `transport` or `type`; supported values are `http`, `streamable_http`, and `sse`.
- `enabled = false` keeps the definition in config without exposing the tools.
- `tool_name_prefix = true` is recommended and is the runtime default.
- `env` values support `${VAR}` interpolation from the runtime process environment.
- `env_from_host` copies selected host environment variables into stdio MCP subprocesses.
- `headers` values for remote MCP servers also support `${VAR}` interpolation.
- remote `auth.mode = "oauth_user_grant"` is supported only for remote MCP servers and may not be combined with static `headers`.
- if any configured remote MCP server uses `oauth_user_grant`, `task.create` must include a `runtime_user_id`.
- Missing interpolated or passthrough variables fail config loading immediately.

Example Atlassian MCP configuration:

```toml
[mcp.servers.mcp_atlassian]
enabled = true
description = "Atlassian Jira and Confluence MCP"
command = "uvx"
args = ["mcp-atlassian"]
env = { JIRA_URL = "https://your-company.atlassian.net", JIRA_USERNAME = "your.email@company.com", JIRA_API_TOKEN = "${JIRA_API_TOKEN}", CONFLUENCE_URL = "https://your-company.atlassian.net/wiki", CONFLUENCE_USERNAME = "your.email@company.com", CONFLUENCE_API_TOKEN = "${CONFLUENCE_API_TOKEN}" }
env_from_host = ["JIRA_API_TOKEN", "CONFLUENCE_API_TOKEN"]
```

### Claude/Deep Agents compatible `.mcp.json` import

The runtime imports project MCP config files that follow the common `mcpServers` JSON shape.

Project root `.mcp.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    "mcp-atlassian": {
      "command": "uvx",
      "args": ["mcp-atlassian"],
      "env": {
        "JIRA_URL": "https://your-company.atlassian.net",
        "JIRA_USERNAME": "your.email@company.com",
        "JIRA_API_TOKEN": "${JIRA_API_TOKEN}",
        "CONFLUENCE_URL": "https://your-company.atlassian.net/wiki",
        "CONFLUENCE_USERNAME": "your.email@company.com",
        "CONFLUENCE_API_TOKEN": "${CONFLUENCE_API_TOKEN}"
      },
      "envFromHost": ["JIRA_API_TOKEN", "CONFLUENCE_API_TOKEN"]
    },
    "remote-api": {
      "type": "http",
      "url": "https://example.com/mcp",
      "headers": {
        "Authorization": "Bearer TOKEN"
      }
    }
  }
}
```

The runtime searches only within the current project root:

- `<project>/.deepagents/.mcp.json`
- `<project>/.mcp.json`

If the same server name appears in more than one source, higher-precedence config replaces the lower-precedence definition entirely.

Supported environment-variable patterns:

- literal values:
  - `"JIRA_URL": "https://your-company.atlassian.net"`
- interpolated values:
  - `"JIRA_API_TOKEN": "${JIRA_API_TOKEN}"`
- explicit host passthrough:
  - `"envFromHost": ["JIRA_API_TOKEN"]`

Precedence within one stdio MCP server definition:

1. interpolated literal `env` entries
2. `env_from_host` / `envFromHost` passthrough keys that are not already explicitly set

### Approval and trust model

MCP server connection is a governed runtime operation.

- Native runtime TOML MCP servers are treated as operator-managed configuration and are allowed by default.
- Imported project stdio MCP servers require approval before they can be launched for a run.
- Imported remote MCP servers follow the runtime web access policy:
  - `web_access_mode = "allow"` allows them
  - `web_access_mode = "require_approval"` pauses for approval
  - `web_access_mode = "deny"` rejects them
- Missing host environment variables are treated as configuration errors, not approval events.
- Remote OAuth authorization, completion, refresh, and revoke are runtime-governed operations separate from `mcp.server.connect`.

Approval boundaries are run-scoped. Approving an MCP server for one run does not persist that approval to unrelated runs.

### Per-user remote OAuth behavior

When a remote MCP server uses `auth.mode = "oauth_user_grant"`:

- the runtime resolves auth headers per run using the task's `runtime_user_id`
- if no valid grant exists, the run pauses with `remote_mcp_authorization_required`
- task snapshots expose server-driven actions such as `remote_mcp.authorize.start`, `remote_mcp.authorize.complete`, `remote_mcp.reauthorize`, and `remote_mcp.revoke`
- the TUI consumes those actions directly and stays provider-agnostic
- static bearer headers remain available for shared-token use cases

The CLI does not yet provide a polished interactive flow for these methods. The TUI is the intended operator experience today.

### Primary agent MCP behavior

The primary agent automatically receives all enabled MCP tools for the run when MCP is allowed by `allowed_capabilities`.

By default, an MCP tool named `echo_text` from server `fixture` is exposed to the model as:

```text
fixture_echo_text
```

This avoids collisions between two MCP servers that export the same tool name.

The primary agent does not need any extra manifest or role configuration. If MCP is enabled in config, the primary agent sees the tools.

### Subagent MCP behavior

Subagents do not automatically inherit MCP tools. A role must explicitly opt in by adding `mcp_tools` to its manifest `tool_scope`.

Example:

```yaml
role_id: researcher
name: Researcher
description: Gather relevant implementation context.
tool_scope:
  - read_files
  - memory_lookup
  - mcp_tools
  - web_fetch
  - web_search
memory_scope:
  - run
  - project
filesystem_scope:
  - workspace
  - memory
```

Current behavior:

- the primary agent always gets enabled MCP tools
- a subagent gets MCP tools only if its `tool_scope` contains `mcp_tools`
- subagent MCP exposure is still filtered by run `allowed_capabilities`
- adding `mcp_tools` does not remove the need for the role’s existing filesystem, memory, or web scopes

The repository baseline currently enables `mcp_tools` for the `researcher` subagent only.

### `allowed_capabilities` interaction

MCP tools participate in runtime capability filtering the same way built-in tools do.

The MCP capability aliases are:

- `mcp_tools`
- `mcp`
- `mcp.tools`

If a run supplies a non-empty `allowed_capabilities` set and none of those aliases are present, MCP tools are not exposed even when MCP is configured.

### Events and observability

Each MCP tool call emits a standard `tool.called` runtime event with extra metadata:

- `server_name`
- `transport`
- `raw_tool_name`
- `exposed_tool_name`
- `tool_source = "mcp"`
- `agent_role`

The MCP adapter also surfaces:

- `mcp.log`
- `mcp.progress`
- `mcp.elicitation.unsupported`

The runtime does not currently support MCP elicitation prompts. If a server requests elicitation, the tool call fails and the runtime emits an unsupported event.

### End-to-end setup example

1. Add an MCP server to the runtime config:

```toml
[mcp]
tool_name_prefix = true

[mcp.servers.fixture_stdio]
enabled = true
command = "python3"
args = ["tests/fixtures/mcp_echo_server.py"]
```

2. Boot the runtime or use the CLI with that config:

```bash
python -m apps.cli.local_agent_cli.cli --config docs/architecture/runtime.example.toml health
```

3. If a subagent should use MCP tools, add `mcp_tools` to that role’s `tool_scope` in `agents/subagents/<role>/manifest.yaml`.

4. Submit a run. The primary agent will see the MCP tools automatically. An opted-in subagent will also see them.

5. If the MCP server came from project `.mcp.json` and uses stdio, approve the startup request when the runtime pauses for approval.

6. If the remote MCP server is OAuth-backed, use the TUI to set the `runtime_user_id`, start authorization, open or copy the returned authorization URL, paste the returned `code` and `state_token`, and then resume the task.

### Troubleshooting

- MCP tools do not appear:
  - confirm the server is `enabled = true`
  - confirm the run did not restrict `allowed_capabilities` to a set that excludes `mcp`, `mcp.tools`, or `mcp_tools`
  - for subagents, confirm the role manifest includes `mcp_tools`
- stdio MCP server fails to launch:
  - run the configured command directly in the shell first
  - verify paths are correct relative to the executable, not relative to the config file unless your command expects that
  - verify every `${VAR}` used in `env` is present in the runtime process environment
  - verify every `env_from_host` / `envFromHost` key exists in the runtime process environment
- remote MCP server fails:
  - verify `transport` and `url`
  - for `static_headers`, verify required headers and every `${VAR}` used in `headers`
  - for `oauth_user_grant`, verify the referenced OAuth provider exists and the task has a `runtime_user_id`
  - check whether runtime `web_access_mode` is requiring approval or denying the connection
- TUI keeps prompting for runtime user ID:
  - set it once in the prompt or command palette; it is persisted to `~/.local-agent-harness/tui-settings.json`
- task pauses with remote MCP authorization required:
  - expected for OAuth-backed remote MCP when the runtime has no valid user grant yet
  - use `authorize`, `complete-auth`, or `revoke-auth` in task detail, or the matching command palette entries
- tool name collisions:
  - keep `mcp.tool_name_prefix = true`
- elicitation errors:
  - expected for now; the runtime does not implement MCP elicitation workflows yet

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
- `agent cancel <task_id> [--run-id <run_id>] [--reason "<reason>"]`
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
- `task.cancel`
- `task.logs.stream`
- `task.artifacts.list`
- `task.artifact.get`
- `memory.inspect`
- `skill.install`
- `config.get`
- `remote_mcp.authorize.start`
- `remote_mcp.authorize.complete`
- `remote_mcp.reauthorize`
- `remote_mcp.revoke`

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
- `memory.updated`
- `skill.install.requested`
- `skill.install.validated`
- `skill.install.approval_requested`
- `skill.install.completed`
- `skill.install.failed`
- `task.completed`
- `task.failed`

The primary agent also has a built-in `memory_write` tool for creating `run_state` and `project` memory records. `project` writes remain governed by the existing memory approval path, while subagents stay read-only for memory in the current baseline.

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
