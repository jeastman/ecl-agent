# ADR-0001 — Runtime/Client Separation

## Status
Accepted

## Date
2026-03-10

## Context

The project is intended to provide a local AI agent harness built around a Python-based LangChain DeepAgent runtime, while also supporting multiple future clients such as CLI and web. There is a strong requirement to maintain clear architectural boundaries and avoid binding core behavior to a single interface.

If the initial CLI becomes the place where orchestration logic, task lifecycle logic, or runtime state lives, the system will become difficult to evolve into a multi-client platform. This would also blur the domain boundaries between user interaction and autonomous execution.

The project mandate emphasizes the Triadic Lens:
- Domain-Driven Design for bounded contexts and ubiquitous language
- Clean Architecture for dependency direction and infrastructure isolation
- HATEOAS-informed interaction thinking for navigable task and artifact state

## Decision

We will separate the system into:
1. **Agent Runtime** — the authoritative execution host for tasks, memory, policy, sandboxing, and sub-agent orchestration
2. **Clients** — user-facing applications such as the CLI and future web UI
3. **Shared Contracts** — transport-neutral schemas for tasks, events, artifacts, approvals, and configuration

The CLI will be a thin client. It may:
- submit tasks
- stream events
- inspect task state
- review artifacts
- answer approval prompts

The CLI will not:
- own orchestration logic
- host persistent task state
- directly implement agent memory semantics
- bypass runtime policy

## Consequences

### Positive
- Enables additional clients without redesigning the core runtime
- Preserves a clean dependency direction
- Keeps agent orchestration in one place
- Simplifies testing of runtime behavior independent of presentation
- Supports future remote or embedded runtime deployment patterns

### Negative
- Introduces contract design work earlier
- Requires explicit event and task schemas up front
- Makes the first implementation slightly more involved than a single-process CLI

## Alternatives Considered

### Single-process CLI application
Rejected because it couples the first UI to the runtime and makes future clients expensive.

### CLI-first with “temporary” embedded runtime logic
Rejected because temporary orchestration logic tends to become permanent and erodes the architecture.

## Architectural Implications

### Domain Boundary
The authoritative domain concepts belong to the runtime, not the CLI:
- Task
- Run
- Artifact
- Approval Request
- Memory Entry
- Policy Decision

### Clean Architecture Rule
Clients depend on shared contracts and SDKs.
The runtime depends on domain interfaces and infrastructure adapters.
The domain does not depend on CLI or LangChain implementation details.

## Follow-up Work
- Define the transport-neutral protocol package
- Define task lifecycle schemas
- Define runtime event envelope
- Create a thin CLI SDK that targets the runtime contract
