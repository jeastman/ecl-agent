# Local Agent Harness

Milestone 0 scaffolds a local-first agent harness monorepo with:

- shared protocol, config, task, identity, and observability packages
- a Python runtime shell exposing JSON-RPC 2.0 over stdio
- a thin CLI client that launches the runtime and calls the shared contract

## Layout

- `apps/cli` thin client entrypoint and stdio transport wrapper
- `apps/runtime` runtime bootstrap and JSON-RPC dispatcher
- `packages/*` shared domain and protocol contracts reused by both apps
- `agents/primary-agent/IDENTITY.md` initial operating identity source
- `docs/architecture` architecture notes and example configuration

## Tooling

The repository uses `uv` for environment and dependency management and `poethepoet` for root-level tasks.

```bash
uv sync --all-groups
uv run poe test
uv run poe health
```

Available top-level tasks:

- `uv run poe sync`
- `uv run poe test`
- `uv run poe lint`
- `uv run poe format`
- `uv run poe typecheck`
- `uv run poe health`
- `uv run poe submit`

## Quick Start

```bash
uv run poe health
uv run poe submit
```
