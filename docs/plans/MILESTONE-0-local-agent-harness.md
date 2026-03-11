# MILESTONE-0 — Local Agent Harness Foundations

## Purpose

Milestone 0 establishes the architectural and implementation foundations for the local AI agent harness monorepo. The objective is not yet to deliver full autonomous execution, but to create the structural base that makes the later DeepAgent runtime, sandboxing, memory, and CLI work coherent and sustainable.

This milestone should leave the project with a working repository skeleton, stable shared schemas, a runtime composition shell, and a thin CLI that can communicate with the runtime over the chosen local protocol.

## Goals

1. Establish the monorepo structure.
2. Define the shared domain and protocol packages.
3. Create a runtime process shell in Python.
4. Create a first CLI shell that talks to the runtime.
5. Introduce identity and configuration loading.
6. Define task and event schemas.
7. Provide basic health and diagnostics flow.

## Non-Goals

- full DeepAgent execution
- sub-agent delegation
- durable memory implementation
- sandboxed command execution
- artifact generation beyond placeholders
- web client support

## Scope

### In Scope

- repository layout
- package boundaries
- config schema
- task contract schema
- event envelope schema
- JSON-RPC 2.0 over stdio integration
- runtime startup and health check
- CLI command for runtime health and basic task submit stub
- `IDENTITY.md` loading and validation
- correlation ID plumbing

### Out of Scope

- actual long-running task completion
- tool execution pipeline
- file editing tools
- command runner
- checkpoints and resumability
- approvals workflow beyond type stubs

## Deliverables

### 1. Monorepo Skeleton
Create the top-level repo layout:

```text
apps/
  cli/
  runtime/
packages/
  protocol/
  config/
  task-model/
  identity/
  observability/
agents/
  primary-agent/
    IDENTITY.md
docs/
  architecture/
  adr/
```

### 2. Shared Protocol Package
Provide canonical schemas for:

- JSON-RPC request/response envelopes
- `task.submit` request
- `runtime.health` response
- event envelope
- task snapshot
- action descriptor

### 3. Shared Config Package
Provide a typed config loader supporting:

- runtime settings
- identity path
- transport mode
- default model config
- sub-agent model override placeholders
- policy placeholders

### 4. Identity Package
Provide:

- `IDENTITY.md` loader
- validation rules
- version/hash generation
- compiled runtime identity bundle structure

### 5. Runtime Shell
Provide a Python runtime application that:

- boots from config
- loads identity bundle
- exposes JSON-RPC over stdio
- supports `runtime.health`
- supports stubbed `task.submit`
- emits structured logs/events with correlation IDs

### 6. CLI Shell
Provide an initial CLI that:

- starts or connects to the runtime
- calls `runtime.health`
- calls stubbed `task.submit`
- renders returned task IDs and status
- surfaces runtime errors cleanly

## Required Domain Artifacts

### Task Status Enum
At minimum:
- `created`
- `accepted`
- `running`
- `awaiting_approval`
- `completed`
- `failed`
- `cancelled`

### Event Types
At minimum:
- `task.created`
- `task.accepted`
- `task.started`
- `task.failed`
- `task.completed`
- `runtime.warning`

### Core IDs
Define stable formats or generation conventions for:
- task ID
- run ID
- event ID
- correlation ID

## Suggested Implementation Approach

### Runtime Language
Python, as the eventual DeepAgent host.

### CLI Language
Defer final language choice, but select one that supports:
- robust command structure
- stdio process control
- JSON serialization
- future packaging/distribution

Good candidate options:
- TypeScript/Node
- Go
- Rust

For Milestone 0, prioritize delivery speed and protocol clarity over long-term optimization.

## Acceptance Criteria

### AC1 — Monorepo Layout Exists
The repository contains the defined top-level structure and clear README notes for each major area.

### AC2 — Config Loads Successfully
The runtime can boot from a config file and validate required settings.

### AC3 — Identity Loads Successfully
The runtime loads `IDENTITY.md`, produces an identity bundle, and fails clearly when the file is missing or invalid.

### AC4 — Runtime Health Works
A client can call `runtime.health` and receive a valid structured response.

### AC5 — Task Submit Stub Works
A client can submit a task contract and receive a stubbed task acceptance response with task ID and initial status.

### AC6 — Correlation IDs Flow End-to-End
Every request/response/event generated through the runtime includes a correlation ID.

### AC7 — Shared Schemas Are Reused
CLI and runtime both depend on the shared protocol/task packages rather than maintaining duplicate schemas.

## QA Checklist

### Repository and Packaging
- [ ] Monorepo structure matches the milestone spec
- [ ] Package boundaries are documented
- [ ] Shared schemas are not duplicated in app code

### Configuration
- [ ] Invalid config produces clear startup errors
- [ ] Missing required fields fail fast
- [ ] Example config is included

### Identity
- [ ] `IDENTITY.md` is loaded from configured path
- [ ] Identity bundle includes version or hash
- [ ] Missing identity file fails clearly

### Runtime Protocol
- [ ] JSON-RPC over stdio is implemented
- [ ] `runtime.health` returns structured runtime information
- [ ] `task.submit` accepts the defined contract shape
- [ ] Error responses follow a consistent schema

### CLI
- [ ] CLI can invoke `runtime.health`
- [ ] CLI can invoke `task.submit`
- [ ] CLI renders task ID and returned status clearly
- [ ] CLI handles runtime not available / invalid response cases

### Observability
- [ ] Correlation IDs are generated and propagated
- [ ] Runtime logs are structured
- [ ] Basic event emission is present for task acceptance

## Exit Criteria

Milestone 0 is complete when the project has a coherent monorepo structure, a transport contract, a runtime shell, a CLI shell, and identity/config/task foundations that are stable enough to support the first real DeepAgent integration in Milestone 1.

## Next Milestone Preview

Milestone 1 should introduce:

- single-agent DeepAgent adapter
- basic workspace sandbox
- event streaming during execution
- real task lifecycle transitions
- initial artifact capture
