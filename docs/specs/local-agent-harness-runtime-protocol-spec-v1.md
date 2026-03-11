# Local Agent Harness — Runtime Protocol Specification v1

**Status:** Draft v1  
**Date:** 2026-03-10  
**Audience:** Runtime engineers, CLI engineers, web/client engineers, protocol implementers, AI coding agents  
**Scope:** Transport-neutral protocol contract for communication between clients and the local agent runtime

---

## 1. Purpose

This specification defines the **runtime protocol** for the Local Agent Harness. The protocol governs communication between:

- the **runtime** (authoritative execution host), and
- one or more **clients** (CLI first, web later)

The protocol is designed to be **transport-neutral**, with the initial implementation using **JSON-RPC 2.0 over stdio**. It supports task submission, task inspection, event streaming, approvals, artifact discovery, configuration inspection, and health/status operations.

This protocol is part of the architecture defined by the master specification and must preserve the runtime/client separation.

---

## 2. Goals

The protocol must:

1. support a **local-first CLI**
2. support **future clients** without redesign
3. separate **requests/responses** from **runtime events**
4. support **long-running tasks**
5. support **streaming progress**
6. support **human approvals**
7. support **artifact discovery and inspection**
8. be understandable to both human developers and AI coding agents

---

## 3. Non-Goals

This specification does not define:

- the internal implementation of the runtime
- the internals of the LangChain DeepAgent adapter
- the final web UI protocol transport
- transport-specific process supervision
- final authentication/authorization requirements for remote deployments

Those are separate concerns.

---

## 4. Protocol Style

### 4.1 Transport-neutral contract

The runtime protocol is defined independently from transport. Message meaning must remain stable across transports.

### 4.2 Initial transport

The first implementation will use:

- **JSON-RPC 2.0 over stdio**

This choice optimizes for local CLI usage while preserving future reuse over:

- WebSocket
- HTTP + Server-Sent Events
- other local IPC mechanisms if needed

### 4.3 Two-channel conceptual model

The protocol has two conceptual channels:

1. **RPC channel**
   - request/response methods
   - command and query semantics

2. **Event channel**
   - runtime-emitted events
   - progress, state changes, approvals, artifacts, diagnostics

In the initial stdio implementation, both may share the same byte stream, but the message types must still remain distinguishable.

---

## 5. Protocol Principles

1. The **runtime is authoritative** for task/run state.
2. Clients are **consumers of protocol contracts**, not owners of runtime logic.
3. All long-running operations must be **observable through events**.
4. Artifacts are **runtime-owned outputs**.
5. Every request and event should be **correlatable** for tracing and debugging.
6. Payloads should be **forward-compatible** through versioned schemas and additive evolution.
7. Event consumers must tolerate receiving **unknown future event types**.

---

## 6. Versioning

### 6.1 Protocol version

The protocol must expose a semantic version string, for example:

```json
{
  "protocol_version": "1.0.0"
}
```

### 6.2 Compatibility guidance

- additive fields are allowed in minor revisions
- field removal or semantic breakage requires a major version change
- clients must ignore unknown fields
- clients must ignore unknown event types unless explicitly required for their UX

### 6.3 Schema ownership

All schemas should live in a shared `packages/protocol/` package in the monorepo.

---

## 7. Core Identifiers

The following identifiers must exist across the protocol:

- `task_id` — stable identifier for the logical task
- `run_id` — stable identifier for a specific execution attempt/session of a task
- `event_id` — stable identifier for an emitted event
- `artifact_id` — stable identifier for a registered artifact
- `approval_id` — stable identifier for an approval request
- `correlation_id` — request/event trace correlation token
- `request_id` — transport/method level request identifier when applicable

### 7.1 ID requirements

Identifiers should be:
- opaque to clients
- globally unique within their domain
- string typed
- stable once issued

---

## 8. Common Envelope Types

### 8.1 RPC request envelope

For JSON-RPC transport, the protocol uses the JSON-RPC 2.0 envelope.

Example:

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "method": "task.create",
  "params": {
    "correlation_id": "corr-123",
    "task": {
      "objective": "Create a parser for the XYZ format"
    }
  }
}
```

### 8.2 RPC response envelope

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "task_id": "task_abc123",
    "run_id": "run_xyz456"
  }
}
```

### 8.3 RPC error envelope

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "error": {
    "code": -32010,
    "message": "Approval required before execution can continue",
    "data": {
      "task_id": "task_abc123",
      "approval_id": "approval_001"
    }
  }
}
```

### 8.4 Event envelope

All runtime-emitted events must use a common envelope:

```json
{
  "type": "runtime.event",
  "protocol_version": "1.0.0",
  "event": {
    "event_id": "evt_001",
    "event_type": "task.started",
    "timestamp": "2026-03-10T18:00:00Z",
    "task_id": "task_abc123",
    "run_id": "run_xyz456",
    "correlation_id": "corr-123",
    "source": {
      "kind": "runtime"
    },
    "payload": {}
  }
}
```

### 8.5 Source object

The `source` object may include:

- `kind` — `runtime`, `subagent`, `tool`, `sandbox`, `memory`, `policy`
- `name` — optional specific name, such as `planner`, `coder`, `shell.execute`
- `role` — optional sub-agent role name
- `component` — optional internal component identifier

---

## 9. Data Types

### 9.1 Timestamp

All timestamps must be RFC 3339 / ISO 8601 UTC strings.

Example:
```json
"2026-03-10T18:00:00Z"
```

### 9.2 Status enums

Initial task status values:

- `created`
- `accepted`
- `planning`
- `executing`
- `awaiting_approval`
- `resuming`
- `completed`
- `failed`
- `cancelled`

### 9.3 Artifact persistence class

Initial values:

- `ephemeral`
- `run`
- `project`

### 9.4 Approval decision values

Initial values:

- `approve`
- `reject`
- `cancel`

---

## 10. Task Submission Contract

### 10.1 TaskCreateRequest

A client creates a task by sending a `task.create` request.

Required fields:

- `objective`
- `workspace_roots`

Recommended fields:

- `scope`
- `success_criteria`
- `constraints`
- `allowed_capabilities`
- `approval_policy`
- `identity_bundle_ref`
- `metadata`

Example:

```json
{
  "objective": "Implement a CLI command that lists artifacts for a task",
  "scope": "Modify the runtime and CLI packages only",
  "success_criteria": [
    "Command exists",
    "Artifacts render in a stable table",
    "Protocol contract is unchanged"
  ],
  "constraints": [
    "Do not change transport framing",
    "Do not introduce direct runtime logic into the CLI"
  ],
  "allowed_capabilities": [
    "read_workspace",
    "write_workspace",
    "execute_commands"
  ],
  "workspace_roots": [
    "/workspace/repo"
  ],
  "approval_policy": {
    "mode": "on_request"
  },
  "identity_bundle_ref": "primary-agent/default",
  "metadata": {
    "submitted_by": "cli"
  }
}
```

### 10.2 TaskCreateResult

The runtime returns:

- `task_id`
- `run_id`
- `status`
- `accepted_at`

Example:

```json
{
  "task_id": "task_abc123",
  "run_id": "run_xyz456",
  "status": "accepted",
  "accepted_at": "2026-03-10T18:01:00Z"
}
```

---

## 11. Task Snapshot Contract

A task snapshot is the canonical query/view model returned by task inspection methods.

### 11.1 TaskSnapshot fields

Required fields:

- `task_id`
- `run_id`
- `status`
- `objective`
- `created_at`
- `updated_at`

Recommended fields:

- `scope`
- `success_criteria`
- `constraints`
- `workspace_roots`
- `current_phase`
- `latest_summary`
- `awaiting_approval`
- `active_subagent`
- `artifact_count`
- `last_event_at`
- `failure`
- `links`

Example:

```json
{
  "task_id": "task_abc123",
  "run_id": "run_xyz456",
  "status": "executing",
  "objective": "Implement a CLI command that lists artifacts for a task",
  "created_at": "2026-03-10T18:01:00Z",
  "updated_at": "2026-03-10T18:05:00Z",
  "current_phase": "executing",
  "latest_summary": "Coder is updating the CLI artifact command.",
  "awaiting_approval": false,
  "active_subagent": "coder",
  "artifact_count": 2,
  "last_event_at": "2026-03-10T18:05:00Z",
  "links": {
    "artifacts": "task.artifacts.list",
    "events": "task.logs.stream"
  }
}
```

---

## 12. Artifact Contract

### 12.1 ArtifactReference

Artifacts must expose metadata sufficient for discovery and rendering.

Required fields:

- `artifact_id`
- `task_id`
- `run_id`
- `logical_path`
- `content_type`
- `created_at`
- `persistence_class`

Recommended fields:

- `source_role`
- `source_tool`
- `byte_size`
- `display_name`
- `summary`
- `downloadable`
- `hash`

Example:

```json
{
  "artifact_id": "art_001",
  "task_id": "task_abc123",
  "run_id": "run_xyz456",
  "logical_path": "artifacts/cli/artifact-list-output.md",
  "content_type": "text/markdown",
  "created_at": "2026-03-10T18:06:00Z",
  "persistence_class": "run",
  "source_role": "coder",
  "display_name": "Artifact List Output",
  "summary": "Rendered example output for the CLI artifacts command.",
  "downloadable": true
}
```

---

## 13. Approval Contract

### 13.1 ApprovalPrompt

Approval prompts are runtime-owned decision requests surfaced to clients.

Required fields:

- `approval_id`
- `task_id`
- `run_id`
- `reason`
- `requested_at`
- `options`

Recommended fields:

- `summary`
- `risk_level`
- `requested_action`
- `context`
- `expires_at`

Example:

```json
{
  "approval_id": "approval_001",
  "task_id": "task_abc123",
  "run_id": "run_xyz456",
  "reason": "Command execution policy requires approval for write access outside the initial task scope.",
  "requested_at": "2026-03-10T18:07:00Z",
  "summary": "The agent wants to modify an additional package not listed in the original scope.",
  "risk_level": "medium",
  "requested_action": "Expand workspace write scope to packages/protocol",
  "options": ["approve", "reject", "cancel"]
}
```

### 13.2 ApprovalDecisionRequest

Clients respond with:

- `approval_id`
- `decision`
- optional `comment`

Example:

```json
{
  "approval_id": "approval_001",
  "decision": "approve",
  "comment": "Approved for protocol package only."
}
```

---

## 14. Method Definitions

## 14.1 `runtime.health`

### Purpose
Returns a basic runtime health and capability view.

### Params
Optional:
- `correlation_id`

### Result
- `status`
- `protocol_version`
- `runtime_version`
- `transport`
- `capabilities`

Example result:

```json
{
  "status": "ok",
  "protocol_version": "1.0.0",
  "runtime_version": "0.1.0",
  "transport": "stdio",
  "capabilities": {
    "task_create": true,
    "event_stream": true,
    "artifacts": true,
    "approvals": true
  }
}
```

---

## 14.2 `config.get`

### Purpose
Returns runtime-visible configuration safe for client inspection.

### Params
Optional:
- `correlation_id`
- `include_effective` (boolean)

### Result
- `effective_config`
- `redactions`
- `loaded_profiles`

Sensitive data must be redacted.

---

## 14.3 `task.create`

### Purpose
Creates and starts a new task execution attempt.

### Params
- `correlation_id`
- `task` (TaskCreateRequest)

### Result
- TaskCreateResult

### Notes
The runtime may begin emitting task events immediately after accepting the task.

---

## 14.4 `task.get`

### Purpose
Returns the latest task snapshot.

### Params
- `correlation_id`
- `task_id`

Optional:
- `run_id`

### Result
- `task` (TaskSnapshot)

---

## 14.5 `task.cancel`

### Purpose
Requests cancellation of a running task.

### Params
- `correlation_id`
- `task_id`

Optional:
- `run_id`
- `reason`

### Result
- `task_id`
- `run_id`
- `status`

### Notes
Cancellation is best-effort. Final confirmation arrives through events and subsequent `task.get`.

---

## 14.6 `task.approve`

### Purpose
Submits an approval decision.

### Params
- `correlation_id`
- `task_id`
- `run_id`
- `approval` (ApprovalDecisionRequest)

### Result
- `task_id`
- `run_id`
- `approval_id`
- `accepted`
- `status`

---

## 14.7 `task.artifacts.list`

### Purpose
Lists artifacts associated with a task/run.

### Params
- `correlation_id`
- `task_id`

Optional:
- `run_id`
- `persistence_class`
- `content_type_prefix`

### Result
- `artifacts` (array of ArtifactReference)

---

## 14.8 `task.logs.stream`

### Purpose
Subscribes the client to runtime events for a task or run.

### Params
- `correlation_id`
- `task_id`

Optional:
- `run_id`
- `from_event_id`
- `include_history` (boolean)

### Result
The RPC result should confirm the stream/subscription creation. Events arrive asynchronously afterward.

Example result:

```json
{
  "task_id": "task_abc123",
  "run_id": "run_xyz456",
  "stream_open": true
}
```

### Notes
For transports that do not support a shared event stream naturally, this method may define a transport-specific subscription handle while preserving logical behavior.

---

## 14.9 `memory.inspect`

### Purpose
Returns runtime-inspectable memory information appropriate for clients.

### Params
Optional:
- `correlation_id`
- `task_id`
- `run_id`
- `scope` (`run_state`, `project`, `identity`, `scratch`)

### Result
- `entries`
- `scope`
- `count`

### Notes
This is inspection-oriented, not a raw backend dump.

---

## 15. Event Definitions

Each event uses the common event envelope and an event-specific payload.

## 15.1 `task.created`

Payload:
- `status`
- `objective`

Example payload:

```json
{
  "status": "created",
  "objective": "Implement a CLI command that lists artifacts for a task"
}
```

## 15.2 `task.started`

Payload:
- `status`
- `started_at`

## 15.3 `plan.updated`

Payload:
- `summary`
- `milestones`
- `current_step`

Example payload:

```json
{
  "summary": "Planner created a three-step execution plan.",
  "milestones": [
    "Inspect current artifact contract",
    "Implement CLI command",
    "Verify output and update docs"
  ],
  "current_step": "Inspect current artifact contract"
}
```

## 15.4 `subagent.started`

Payload:
- `role`
- `model_profile`
- `objective`

## 15.5 `subagent.completed`

Payload:
- `role`
- `summary`
- `outcome`

## 15.6 `tool.called`

Payload:
- `tool_name`
- `tool_kind`
- `summary`

Optional:
- `command`
- `path`
- `result_class`

## 15.7 `artifact.created`

Payload:
- `artifact` (ArtifactReference)

## 15.8 `approval.requested`

Payload:
- `approval` (ApprovalPrompt)

## 15.9 `memory.updated`

Payload:
- `scope`
- `summary`
- `entry_count_delta`

## 15.10 `task.completed`

Payload:
- `status`
- `completed_at`
- `summary`
- `outcome`

## 15.11 `task.failed`

Payload:
- `status`
- `failed_at`
- `summary`
- `error`

Example payload:

```json
{
  "status": "failed",
  "failed_at": "2026-03-10T18:10:00Z",
  "summary": "Task failed during verification.",
  "error": {
    "code": "verification_error",
    "message": "Unit tests failed after CLI changes."
  }
}
```

---

## 16. Error Model

### 16.1 Goals

Errors must be:
- structured
- user-displayable
- machine-actionable where appropriate
- traceable

### 16.2 Error fields

Structured error `data` should include, where relevant:

- `task_id`
- `run_id`
- `approval_id`
- `correlation_id`
- `retryable`
- `category`
- `details`

### 16.3 Suggested categories

- `validation_error`
- `not_found`
- `conflict`
- `approval_required`
- `policy_denied`
- `runtime_unavailable`
- `sandbox_error`
- `memory_error`
- `internal_error`

### 16.4 Example

```json
{
  "code": -32020,
  "message": "Task not found",
  "data": {
    "category": "not_found",
    "task_id": "task_missing",
    "retryable": false
  }
}
```

---

## 17. Ordering and Delivery Semantics

### 17.1 Event ordering

Within a given `run_id`, the runtime should emit events in causal order whenever practical.

Clients must still tolerate:
- delayed delivery
- duplicate delivery in future transports
- unknown event types
- minor reordering in edge cases

### 17.2 Idempotency guidance

- `task.get` and `task.artifacts.list` are naturally idempotent
- `task.approve` should reject duplicate final decisions for the same `approval_id`
- `task.create` may support future client-provided idempotency keys, but this is not required in v1

### 17.3 Resumption guidance

Clients may reconnect and resume event viewing through:
- `task.get`
- `task.logs.stream` with `from_event_id`

---

## 18. Security and Redaction Guidance

Even in a local-first environment:

- the runtime must redact secrets from `config.get`
- event payloads should avoid leaking sensitive configuration
- artifacts should only be discoverable through runtime-managed references
- clients should not assume direct filesystem access to runtime artifacts

---

## 19. Transport Mapping Guidance

### 19.1 JSON-RPC over stdio

Initial mapping:
- requests are standard JSON-RPC requests
- responses are standard JSON-RPC responses
- events are emitted as JSON objects with `type: "runtime.event"`

### 19.2 Future WebSocket

Possible mapping:
- RPC calls remain request/response messages
- events are pushed on the same socket with the same event envelope

### 19.3 Future HTTP + SSE

Possible mapping:
- RPC-style command/query methods over HTTP
- events streamed via SSE using the same event envelope payload

Transport adapters may vary, but the logical method and event contracts must remain the same.

---

## 20. Package Layout Recommendation

The protocol package should contain:

```text
packages/protocol/
  schemas/
    rpc/
    events/
    task/
    artifacts/
    approvals/
    memory/
    config/
  examples/
  README.md
```

Suggested implementation artifacts:
- schema definitions
- language-friendly typed wrappers
- sample request/response/event payloads
- compatibility notes

---

## 21. Acceptance Criteria

This protocol specification is satisfied for v1 when:

1. The runtime exposes JSON-RPC methods over stdio for the defined initial method set.
2. The runtime emits event envelopes that conform to the common event contract.
3. `task.create`, `task.get`, `task.cancel`, `task.approve`, `task.artifacts.list`, `task.logs.stream`, `config.get`, `memory.inspect`, and `runtime.health` exist.
4. Task snapshots, artifact references, and approval prompts use stable structured shapes.
5. Errors are structured and category-bearing.
6. Clients can correlate requests, task state, runs, approvals, artifacts, and events.
7. The protocol package is transport-neutral and reusable by future clients.

---

## 22. Example End-to-End Flow

### 22.1 Create task

Request:
```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "method": "task.create",
  "params": {
    "correlation_id": "corr-001",
    "task": {
      "objective": "Generate an ADR index command for the CLI",
      "workspace_roots": ["/workspace/repo"],
      "allowed_capabilities": ["read_workspace", "write_workspace", "execute_commands"]
    }
  }
}
```

Response:
```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "task_id": "task_001",
    "run_id": "run_001",
    "status": "accepted",
    "accepted_at": "2026-03-10T19:00:00Z"
  }
}
```

### 22.2 Stream opens

Request:
```json
{
  "jsonrpc": "2.0",
  "id": "req-002",
  "method": "task.logs.stream",
  "params": {
    "correlation_id": "corr-001",
    "task_id": "task_001",
    "run_id": "run_001"
  }
}
```

### 22.3 Events arrive

```json
{
  "type": "runtime.event",
  "protocol_version": "1.0.0",
  "event": {
    "event_id": "evt_001",
    "event_type": "task.started",
    "timestamp": "2026-03-10T19:00:01Z",
    "task_id": "task_001",
    "run_id": "run_001",
    "correlation_id": "corr-001",
    "source": { "kind": "runtime" },
    "payload": {
      "status": "executing",
      "started_at": "2026-03-10T19:00:01Z"
    }
  }
}
```

```json
{
  "type": "runtime.event",
  "protocol_version": "1.0.0",
  "event": {
    "event_id": "evt_002",
    "event_type": "subagent.started",
    "timestamp": "2026-03-10T19:00:05Z",
    "task_id": "task_001",
    "run_id": "run_001",
    "correlation_id": "corr-001",
    "source": { "kind": "subagent", "role": "coder", "name": "coder" },
    "payload": {
      "role": "coder",
      "model_profile": "models.subagents.coder",
      "objective": "Implement the ADR index CLI command"
    }
  }
}
```

### 22.4 Task completes

```json
{
  "type": "runtime.event",
  "protocol_version": "1.0.0",
  "event": {
    "event_id": "evt_010",
    "event_type": "task.completed",
    "timestamp": "2026-03-10T19:05:00Z",
    "task_id": "task_001",
    "run_id": "run_001",
    "correlation_id": "corr-001",
    "source": { "kind": "runtime" },
    "payload": {
      "status": "completed",
      "completed_at": "2026-03-10T19:05:00Z",
      "summary": "CLI ADR index command implemented and verified.",
      "outcome": {
        "result_class": "success"
      }
    }
  }
}
```

---

## 23. Open Questions

1. Should `task.logs.stream` be replaced with a broader `task.events.subscribe` name before implementation?
2. Should v1 include a dedicated `artifact.get` or only `task.artifacts.list`?
3. Should a future `task.resume` method be reserved now?
4. Should idempotency keys be required for `task.create` in Milestone 1 or deferred?

---

## 24. Recommended Next Artifact

The next specification should be the **Milestone 0 Implementation Specification**, translating this protocol contract into:
- package skeletons
- concrete schema files
- CLI command surface
- runtime process framing
- initial fake/runtime stub behavior
