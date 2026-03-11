# Local Agent Harness — Master Specification v1

**Status:** Draft v1  
**Date:** 2026-03-10  
**Audience:** Architects, platform engineers, runtime engineers, CLI/client engineers, AI coding agents  
**Scope:** Foundational architecture and Milestone 0–1 implementation guidance for a local AI agent harness and initial CLI client

---

## 1. Purpose

This specification defines the architecture for a **local AI agent harness** implemented in a **monorepo**, with an initial **CLI client** and a Python-based **runtime service** built around a **LangChain DeepAgent**.

The system exists to provide a **tailored execution harness** for an autonomous agent that operates according to project-defined doctrine in `IDENTITY.md`, works persistently toward a task objective, and delegates work to sub-agents for long-running and multi-step tasks.

This specification establishes the core platform shape, the domain model, the runtime/client separation, the protocol, the backend abstractions, and the first implementation milestones. It also consolidates the foundational architecture decisions captured in the ADR pack.

---

## 2. Vision

The project should evolve into a **local-first agent platform** rather than a one-off terminal assistant.

The first release should deliver:

- a dedicated runtime that hosts the DeepAgent and its supporting backends
- a thin CLI that communicates with the runtime through a formal protocol
- durable architecture boundaries that support future clients such as web
- explicit identity, policy, memory, and sandbox controls
- an extensible sub-agent model with configurable models per role

The system should embody the **Triadic Lens**:

- **Domain-Driven Design** — bounded contexts, ubiquitous language, explicit domain contracts
- **Clean Architecture** — dependency inversion, infrastructure isolation, framework containment
- **HATEOAS-informed interaction thinking** — task state and artifact state exposed as navigable resources/events rather than ad hoc blobs

---

## 3. Governing Principles

### 3.1 Product and architectural principles

1. The **runtime** is the system of record for task execution.
2. The **CLI is a client**, not the application core.
3. Framework-specific concepts must not leak into the domain model.
4. Filesystem access and command execution are **granted capabilities**, not implicit rights.
5. Memory must be governed through explicit categories and scope rules.
6. Identity and policy must be sourced from controlled project artifacts and configuration.
7. The initial architecture must optimize for **future clients** without prematurely requiring a distributed deployment.
8. The system must remain understandable to human developers and AI coding agents working in the monorepo.

### 3.2 Agent behavior principles

The agent operates under project doctrine, with `IDENTITY.md` as a primary behavioral source. The harness should assume that the agent is intended to:

- operate persistently and autonomously toward a declared objective
- decompose and plan work
- use sub-agents to manage complexity and context boundaries
- work within explicit capability and policy constraints
- produce inspectable artifacts, events, and outcomes

---

## 4. External Platform Assumptions

The architecture is intentionally aligned with the current Deep Agents capability model:

- Deep Agents are positioned as an **agent harness** with built-in planning, filesystem tools, subagent-spawning, and long-term memory support.
- Deep Agents use **pluggable backends** for file operations and can expose an `execute` tool via shell/sandbox backends.
- Deep Agents support **CompositeBackend** routing, enabling different path prefixes to map to different storage backends.
- Deep Agents support **custom subagents**, **skills**, **streaming**, and **configurable model providers**.
- LangChain documents two sandbox integration patterns: **agent-in-sandbox** and **sandbox-as-tool**; this project will begin with the **sandbox-as-tool** style runtime shape.

These assumptions inform the architecture but do not replace project-owned abstractions.

---

## 5. In Scope

This specification covers:

- monorepo structure
- bounded contexts and context relationships
- runtime/client split
- transport and protocol contract shape
- task model
- backend abstractions
- memory taxonomy
- sandbox and filesystem policy
- sub-agent strategy
- configuration model
- observability/event model
- milestone sequencing for initial implementation

---

## 6. Out of Scope

This specification does not fully define:

- the future web UI
- advanced distributed deployment
- production remote sandbox infrastructure
- final persistence engine choice beyond initial abstractions
- final approval UX details beyond contract shape
- final skill authoring conventions beyond initial directory placement

These are follow-on specifications.

---

## 7. System Overview

The platform consists of three major top-level parts:

1. **Agent Runtime**
   - Python-based runtime process
   - hosts the DeepAgent adapter
   - owns task execution, memory, policy, sandboxing, artifact capture, and event streaming

2. **Clients**
   - initial CLI client
   - future web client and possibly other interfaces
   - consume protocol methods/events exposed by the runtime

3. **Shared Contracts**
   - protocol schemas
   - configuration schemas
   - domain event envelopes
   - task and artifact contracts

### 7.1 High-level flow

1. A client submits a task to the runtime.
2. The runtime normalizes the request into an internal task contract.
3. The runtime builds or resumes an execution context.
4. The runtime invokes the DeepAgent harness through project-owned ports/adapters.
5. The agent plans, delegates, reads/writes files, updates memory, executes commands, and emits events.
6. Artifacts and state are captured by the runtime.
7. The client streams progress and can inspect state or respond to approvals.
8. The runtime records the final outcome and preserves any approved durable memory/artifacts.

---

## 8. Bounded Contexts

### 8.1 Task Orchestration Context
**Purpose:** Own task lifecycle, run lifecycle, status, checkpoints, and outcome contracts.

**Core concepts:**
- Task
- Run
- TaskObjective
- SuccessCriteria
- TaskConstraint
- TaskStatus
- ApprovalRequest
- Outcome

### 8.2 Agent Runtime Context
**Purpose:** Own agent composition, model resolution, sub-agent registry, skills loading, middleware, and execution flow.

**Core concepts:**
- AgentHarness
- RuntimeSession
- SubAgentRole
- ModelProfile
- ToolScope
- SkillRegistry

### 8.3 Execution Sandbox Context
**Purpose:** Own file access, command execution, environment shaping, path isolation, and execution capture.

**Core concepts:**
- Sandbox
- WorkspaceZone
- ScratchZone
- MemoryZone
- ExecutionRequest
- ExecutionResult
- PathPolicy

### 8.4 Memory Context
**Purpose:** Own task-local and durable memory semantics, retrieval precedence, and provenance.

**Core concepts:**
- RunStateMemory
- ProjectMemory
- IdentityMemory
- ScratchMemory
- MemoryEntry
- MemoryScope
- MemoryPromotionPolicy

### 8.5 Identity and Policy Context
**Purpose:** Own `IDENTITY.md`, capability constraints, approval policy, and doctrine ingestion.

**Core concepts:**
- IdentityBundle
- PolicyDecision
- CapabilityGrant
- ApprovalPolicy
- GuardrailRule

### 8.6 Client Interaction Context
**Purpose:** Own protocol methods, event envelopes, rendering-friendly message shapes, and task inspection contracts.

**Core concepts:**
- RpcMethod
- EventEnvelope
- ArtifactReference
- TaskSnapshot
- ApprovalPrompt

### 8.7 Observability Context
**Purpose:** Own logs, traces, event correlation, and task/run diagnostics.

**Core concepts:**
- CorrelationId
- RunTrace
- EventRecord
- SpanMetadata

---

## 9. Context Relationships

### 9.1 Relationship summary

- **Clients** interact only through the **Client Interaction Context**.
- **Task Orchestration** drives the **Agent Runtime**.
- **Agent Runtime** depends on **Identity and Policy**, **Memory**, and **Execution Sandbox** through ports.
- **Observability** listens to all major runtime activities.
- **Memory** and **Sandbox** are infrastructure-shaped contexts but still retain domain semantics around scope and policy.

### 9.2 Upstream/downstream guidance

- Task Orchestration is upstream of execution flow.
- Identity/Policy is upstream of capability decisions.
- Agent Runtime is upstream of sandbox tool usage and memory operations.
- Client Interaction is downstream of runtime events and state.

---

## 10. Architectural Style

### 10.1 Clean Architecture rules

The system should follow these dependency rules:

- **Domain layer** defines business concepts and interfaces.
- **Application layer** coordinates use cases and orchestrates domain services.
- **Infrastructure layer** implements adapters for DeepAgent, storage, filesystem, shell, tracing, and transport.
- **Clients** depend on transport SDKs and shared contracts.
- The **domain layer must not depend on LangChain, CLI code, or transport details**.

### 10.2 Framework containment rule

LangChain DeepAgent is a framework dependency. It must be **contained behind adapter boundaries**. Only the adapter layer may directly construct or manipulate DeepAgent-specific objects.

---

## 11. Runtime/Client Separation

The runtime is the authoritative host for:

- task submission normalization
- run lifecycle
- memory semantics
- policy enforcement
- sandbox access
- sub-agent orchestration
- artifact management
- event production

The CLI may:

- create tasks
- stream and render runtime events
- inspect status and artifacts
- answer approvals
- request memory/config inspection

The CLI may not:

- own orchestration logic
- store authoritative run state
- directly execute sandbox operations on behalf of the runtime
- implement alternate policy paths

This rule is mandatory.

---

## 12. Monorepo Structure

A recommended initial layout:

```text
repo/
  apps/
    cli/
    runtime/
    web/

  packages/
    protocol/
    config/
    task-model/
    identity/
    observability/
    sdk-client/
    sdk-runtime/

  services/
    deepagent-runtime/
    memory-service/
    sandbox-service/
    artifact-service/
    policy-service/

  agents/
    primary-agent/
      IDENTITY.md
      SYSTEM_PROMPT.md
      skills/
    subagents/
      planner/
      researcher/
      coder/
      verifier/
      librarian/

  docs/
    architecture/
    adr/
    specs/
```

### 12.1 Notes

- `apps/` contains user-facing applications.
- `packages/` contains shared contracts and reusable libraries.
- `services/` contains runtime-facing service implementations and composition roots.
- `agents/` contains doctrine, prompts, skills, and role-specific agent assets.
- `docs/adr/` contains the ADR pack.
- `docs/specs/` contains this master specification and follow-on specs.

---

## 13. Technology Direction

### 13.1 Runtime
- **Language:** Python
- **Reason:** alignment with LangChain DeepAgent

### 13.2 CLI
- **Language:** TBD
- **Rule:** must consume the formal runtime protocol; may not assume in-process Python bindings

### 13.3 Protocol
- **Initial transport:** JSON-RPC 2.0 over stdio
- **Future transports:** WebSocket and/or HTTP + SSE

### 13.4 Configuration
- File-based configuration with environment overlay support
- explicit model routing by role
- explicit workspace/runtime policy settings

---

## 14. Protocol Specification

### 14.1 Protocol goals

The protocol must support:

- local-first usage
- request/response interactions
- event streaming
- approvals
- task inspection
- artifact discovery
- future transport reuse

### 14.2 Initial transport decision

The initial implementation will use **JSON-RPC 2.0 over stdio**.

Rationale:
- ideal for local CLI + runtime process
- easy to debug
- avoids premature daemon assumptions
- keeps the contract transport-neutral

### 14.3 Method surface

Initial methods:

- `task.create`
- `task.get`
- `task.cancel`
- `task.approve`
- `task.artifacts.list`
- `task.logs.stream`
- `config.get`
- `memory.inspect`
- `runtime.health`

### 14.4 Event surface

Initial event types:

- `task.created`
- `task.started`
- `plan.updated`
- `subagent.started`
- `subagent.completed`
- `tool.called`
- `artifact.created`
- `approval.requested`
- `memory.updated`
- `task.completed`
- `task.failed`

### 14.5 Envelope shape

All events should include:

- `event_id`
- `event_type`
- `task_id`
- `run_id`
- `timestamp`
- `correlation_id`
- `payload`

All request/response messages should include stable correlation fields for logging and tracing.

---

## 15. Task Model

### 15.1 Task submission contract

Every task request should include:

- objective
- scope
- success criteria
- constraints
- allowed capabilities
- workspace root(s)
- approval policy
- identity bundle version/reference
- optional task metadata

### 15.2 Internal task normalization

The runtime should convert external requests into an internal task contract that becomes the canonical input to execution.

This normalized form should be explicit and deterministic so that:
- resumability is easier
- policy evaluation is consistent
- logging and debugging are clearer

### 15.3 Lifecycle

Illustrative lifecycle:

1. Created
2. Accepted
3. Planning
4. Executing
5. AwaitingApproval
6. Resuming
7. Completed
8. Failed
9. Cancelled

---

## 16. DeepAgent Adapter Boundary

The runtime must define project-owned ports such as:

- `AgentHarness`
- `TaskRunner`
- `ModelResolver`
- `SubAgentRegistry`
- `MemoryStore`
- `ExecutionSandbox`
- `ArtifactStore`
- `PolicyEngine`

The LangChain implementation will live behind an adapter, for example:

- `LangChainDeepAgentHarness`

### 16.1 Boundary rule

Only the adapter layer may:

- construct DeepAgent instances
- bind framework middleware
- translate framework callbacks into runtime events
- map project model routing into framework model configuration
- map project skills/subagents into DeepAgent configuration

### 16.2 Why this matters

This preserves:
- framework isolation
- testability
- portability
- domain language integrity

---

## 17. Memory Model

### 17.1 Memory taxonomy

The system will distinguish:

1. **Run State Memory**
   - active task state
   - execution summaries
   - checkpoints
   - scoped to the current run/thread

2. **Project Memory**
   - durable conventions and reusable knowledge
   - scoped to a project or workspace

3. **Identity and Policy Memory**
   - sourced from `IDENTITY.md` and controlled config
   - governed input, not freeform agent-authored memory

4. **Ephemeral Scratch Memory**
   - temporary notes
   - transient intermediate state
   - not automatically durable

### 17.2 Memory rules

- project memory requires explicit promotion rules
- identity/policy material originates from controlled files and config
- retrieval precedence should favor identity/policy and task-local relevance before broad durable recall
- all durable memory should preserve provenance and scope metadata

### 17.3 Initial implementation

Initial implementation should support:
- run-local memory
- project memory via a durable store-backed abstraction
- identity ingestion from repository/project files

---

## 18. Sandbox and Filesystem Policy

### 18.1 Filesystem zones

The runtime will expose a governed workspace with explicit zones:

- **Workspace Zone** — project/task files
- **Scratch Zone** — ephemeral outputs
- **Memory Zone** — runtime-managed durable memory files

### 18.2 Policy rules

- no unrestricted host filesystem access
- all visible paths must be normalized through the sandbox layer
- command execution occurs only through the runtime-controlled sandbox interface
- artifact import/export is separate from agent file tools
- future approvals may gate sensitive execution operations

### 18.3 Execution model

The initial system should support a sandbox/tool shape that allows the runtime to stay outside the sandbox while delegating execution/file operations through controlled backends.

This aligns with the preferred local-first harness architecture because:
- agent state remains in the runtime
- sandbox failures are easier to isolate
- future provider-backed sandboxes remain possible

---

## 19. Sub-Agent Strategy

### 19.1 Initial roles

The system should define explicit architectural roles:

- **Planner**
  - decomposes objectives
  - proposes milestones and next steps

- **Researcher**
  - gathers facts, docs, and constraints
  - synthesizes relevant information

- **Coder**
  - writes and modifies implementation artifacts

- **Verifier**
  - evaluates outputs against criteria
  - runs tests/checks where applicable

- **Librarian**
  - helps with retrieval, memory support, and conventions

### 19.2 Role rules

Each role should have:
- purpose
- allowed tools
- file scope
- model profile
- output expectations
- optional role-specific prompt/policy overlays

### 19.3 Design intent

Sub-agents exist to create:
- context quarantine
- specialization
- clearer observability
- more predictable autonomy

---

## 20. Model Routing

The configuration model must support different models for:
- the primary agent
- each sub-agent role
- future overrides by environment or task class

Illustrative shape:

```toml
[models.default]
provider = "openai"
model = "gpt-5"

[models.primary_agent]
provider = "anthropic"
model = "claude-sonnet-4-5"

[models.subagents.planner]
provider = "anthropic"
model = "claude-sonnet-4-5"

[models.subagents.researcher]
provider = "openai"
model = "gpt-5-mini"

[models.subagents.coder]
provider = "openai"
model = "gpt-5"

[models.subagents.verifier]
provider = "anthropic"
model = "claude-sonnet-4-5"
```

### 20.1 Model routing rules

- the runtime owns model resolution
- clients do not choose sub-agent internals directly
- routing should remain inspectable and testable
- model selection should be separable from role definition

---

## 21. Identity and Policy

### 21.1 Identity bundle

The runtime should load an identity bundle composed from:
- `IDENTITY.md`
- controlled policy/config files
- optional role-specific overlays

### 21.2 Policy domains

Initial policy concerns:

- allowed capabilities
- approval thresholds
- workspace boundaries
- memory promotion rules
- artifact publishing rules

### 21.3 Enforcement

Identity and policy should affect:
- agent prompt construction
- tool exposure
- sandbox access
- memory persistence behavior
- approval generation

---

## 22. Skills

The agent should support skill directories stored under project-owned paths in the monorepo.

Suggested initial location:

```text
agents/primary-agent/skills/
agents/subagents/<role>/skills/
```

Skills are a project capability, not a CLI concern. The runtime owns:
- skill discovery
- skill loading
- skill exposure to the agent

---

## 23. Observability and Eventing

### 23.1 Event stream

The runtime should produce an append-only event stream for every run.

### 23.2 Event requirements

Every event should support:
- task/run correlation
- wall-clock timestamp
- event type
- payload schema
- optional source role/tool metadata

### 23.3 Logs and traces

The runtime should maintain:
- structured logs
- task/run correlated events
- trace-friendly metadata
- adapter points for tracing systems

### 23.4 Intent

The event stream is both:
- a client UX substrate
- an operational debugging substrate

---

## 24. Artifact Model

Artifacts should be first-class outputs of runtime execution.

Artifact categories may include:
- generated files
- reports
- logs
- patches
- code outputs
- summaries

Artifact metadata should include:
- artifact id
- task id
- run id
- logical path
- source role
- content type
- creation timestamp
- persistence class

The agent may create files in the sandbox, but the runtime owns artifact registration and export semantics.

---

## 25. Security and Safety Position

This is a local-first tool, but autonomy increases risk. Therefore:

- the host system must not be exposed as a raw tool surface
- the agent must operate through governed filesystem and execution interfaces
- policy enforcement must remain in the runtime
- future human-in-the-loop approvals must be supported without redesign
- secrets handling should remain outside the sandbox where possible

---

## 26. Milestone Plan

### 26.1 Milestone 0 — Foundations
Deliver:
- monorepo skeleton
- shared protocol package
- shared config package
- shared task model package
- runtime composition shell
- IDENTITY ingestion shell
- thin CLI shell
- ADR pack committed under `docs/adr/`

### 26.2 Milestone 1 — Single-Agent Runtime
Deliver:
- one primary DeepAgent through the adapter boundary
- local controlled backend/sandbox implementation
- basic task execution
- event streaming
- artifact capture
- run-local memory

### 26.3 Milestone 2 — Durable Harness
Deliver:
- durable project memory
- checkpoints/resumption
- approval contract and policy engine
- richer observability
- memory inspection support

### 26.4 Milestone 3 — Sub-Agent System
Deliver:
- sub-agent registry
- role-based tool scopes
- model routing
- planner/researcher/coder/verifier flow

### 26.5 Milestone 4 — Multi-Client Platform
Deliver:
- web client
- richer task inspection
- artifact browser
- live event visualization

---

## 27. Implementation Guidance for AI Coding Agents

AI coding agents working in this monorepo should follow these rules:

1. Do not collapse runtime and CLI responsibilities.
2. Do not introduce direct LangChain dependencies into the shared domain/task packages.
3. Do not bypass the sandbox abstraction for convenience.
4. Do not treat memory as an untyped blob store.
5. Do not place model routing logic inside the client.
6. Prefer ports/interfaces first, adapters second.
7. Preserve explicit ubiquitous language across package boundaries.

---

## 28. Acceptance Criteria

This specification is satisfied for the initial architecture baseline when:

1. The monorepo contains distinct runtime and CLI applications.
2. The runtime exposes a transport-neutral protocol contract implemented over stdio.
3. Task execution responsibility resides in the runtime.
4. LangChain DeepAgent is isolated behind project-owned ports/adapters.
5. Memory taxonomy exists as explicit concepts in the codebase.
6. Sandbox/filesystem access is mediated by a dedicated abstraction.
7. Model routing supports separate profiles for primary and sub-agents.
8. `IDENTITY.md` ingestion exists as a runtime concern.
9. Event streaming exists for task lifecycle visibility.
10. The codebase structure clearly supports future clients.

---

## 29. Open Questions

These should be resolved in follow-on specs and implementation ADRs:

1. What language should the CLI use?
2. What exact persistence backend should back durable project memory first?
3. What approval prompts and escalation thresholds should exist in v1?
4. Should the runtime process be long-lived or spawned per CLI command during Milestone 0?
5. What artifact export/import UX is best for the CLI?
6. When should remote/provider-backed sandboxes be introduced?

---

## 30. Recommended Follow-on Specs

The next specs should be:

1. **Runtime Protocol Specification**
2. **Milestone 0 Implementation Specification**
3. **Sandbox Interface Specification**
4. **Memory Retrieval and Promotion Specification**
5. **Sub-Agent Registry Specification**
6. **CLI UX Specification**

---

## 31. ADR Alignment

This master spec incorporates the following accepted architecture decisions:

- ADR-0001 — Runtime/Client Separation
- ADR-0002 — Transport Strategy
- ADR-0003 — DeepAgent Adapter Boundary
- ADR-0004 — Memory Taxonomy and Persistence
- ADR-0005 — Sandbox and Filesystem Policy
- ADR-0006 — Sub-Agent and Model Routing Strategy

---

## 32. Appendix A — Reference Notes

This specification is informed by the current Deep Agents documentation, especially around:
- overview and harness capabilities
- backends and composite routing
- sandboxes and execution patterns
- long-term memory
- subagents
- streaming
- skills
- configuration and providers

The project architecture remains project-owned and may diverge where necessary to maintain Triadic Lens integrity.
