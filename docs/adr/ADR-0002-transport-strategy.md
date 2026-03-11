# ADR-0002 — Transport Strategy

## Status
Accepted

## Date
2026-03-10

## Context

The runtime and client must communicate through a protocol that works well for local-first operation while remaining extensible to future clients such as a web UI.

The initial client is a CLI. The runtime is local. The interaction model must support:
- task submission
- streaming progress
- approvals
- artifact discovery
- inspection of task state
- eventual support for additional clients

The protocol should not prematurely force a network-first deployment model, but it should also avoid a dead-end local integration pattern.

## Decision

We will define a **transport-neutral application protocol** and implement:

- **Primary initial transport:** JSON-RPC 2.0 over stdio
- **Planned future transports:** WebSocket and/or HTTP + Server-Sent Events

The protocol contract will be owned separately from the transport and will define:
- request/response methods
- event envelopes
- artifact references
- approval prompts
- error contracts

## Rationale

### Why stdio first
- Excellent local developer experience
- Low operational complexity
- Avoids premature daemon/server assumptions
- Works naturally for a local CLI launching a runtime process
- Easy to debug and inspect

### Why JSON-RPC
- Simple method semantics
- Clear request/response correlation
- Mature framing model
- Straightforward mapping to future socket-based transports

### Why transport-neutral contracts
The same domain protocol should survive transport changes. This protects the client ecosystem and prevents transport concerns from leaking into core task semantics.

## Consequences

### Positive
- Fast path to a working local CLI
- Future-ready protocol
- Clean separation between message semantics and transport mechanics
- Allows transport adapters to evolve independently

### Negative
- Requires clear distinction between streamed events and RPC responses
- Adds some up-front schema discipline
- May later require minor adaptation for browser compatibility depending on chosen web transport

## Alternatives Considered

### Direct Python bindings from CLI into runtime
Rejected because it couples the client to Python implementation details and prevents language-independent clients.

### REST only
Rejected because it is awkward for local stdio use and less natural for rich streaming workflows in the initial phase.

### gRPC
Rejected for the initial phase because it adds unnecessary complexity and cross-language machinery for a local-first tool.

## Initial Method Surface

Illustrative methods:
- `task.create`
- `task.get`
- `task.cancel`
- `task.approve`
- `task.artifacts.list`
- `config.get`
- `memory.inspect`

Illustrative event types:
- `task.created`
- `task.started`
- `plan.updated`
- `subagent.started`
- `tool.called`
- `artifact.created`
- `approval.requested`
- `task.completed`
- `task.failed`

## Follow-up Work
- Define JSON schemas for protocol envelopes
- Define event ordering and correlation rules
- Implement stdio transport adapter in runtime
- Implement thin client transport library
