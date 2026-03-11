# Local Agent Harness Architecture Specification v1

## 1. Purpose

This document defines the initial architecture for a **local AI agent harness** and its first client, a **CLI tool**, implemented as a monorepo. The system is intended to host an autonomous, long-running agent built on **LangChain Deep Agents** in Python, with support for sub-agents, execution sandboxes, memory, model routing, and future multi-client interaction.

The core intent is not to build a generic chat shell. It is to build a **tailored agent runtime** that can operate relentlessly against a user task while remaining grounded in a strong architectural model, explicit identity, bounded capabilities, and clean separation of concerns.

This specification is guided by the **Triadic Lens**:

- **Domain-Driven Design** for clear bounded contexts and ubiquitous language
- **Clean Architecture** for stable core abstractions and replaceable infrastructure
- **HATEOAS-inspired interaction principles** for progressive, protocol-driven clients that discover actions from runtime state rather than embedding orchestration logic

## 2. Product Intent

The system exists to enable a user to submit a task to an autonomous agent harness that:

- works from a defined operating identity (`IDENTITY.md`)
- plans and executes multi-step work over time
- delegates to specialized sub-agents
- uses controlled tools, memory, and execution environments
- produces durable artifacts and inspectable progress
- remains accessible through a clean client/runtime protocol

The **CLI** is only the first client. The architecture must support future clients such as:

- web UI
- TUI
- editor integrations
- external orchestration or automation surfaces

## 3. Architectural Vision

The system is split into three major concerns:

### 3.1 Control Plane
Owns configuration, policy, identity, task lifecycle, approvals, observability, and client-facing protocol contracts.

### 3.2 Agent Runtime
Owns the Python-hosted DeepAgent harness, sub-agent execution, memory, skills, middleware, model routing, and sandbox integration.

### 3.3 Clients
Own the user experience for interacting with the runtime: submitting tasks, inspecting progress, reviewing artifacts, and answering runtime prompts.

This keeps the CLI from becoming the application. The CLI is a consumer of runtime capabilities, not the place where agent behavior is defined.

## 4. Key Principles

1. **The runtime is the product core.** The CLI is a client.
2. **Identity and policy are first-class.** Agent autonomy is bounded by explicit operating principles.
3. **The domain must not depend on LangChain types.** LangChain is an adapter, not the center of the system.
4. **Memory is not a blob.** Distinguish run state, project memory, and identity/policy memory.
5. **Sandbox access must be rooted and governed.** Never expose unconstrained host access.
6. **Protocol contracts are transport-agnostic.** Stdio first, sockets later.
7. **Event streams are the system spine.** Clients should observe task state through durable runtime events.
8. **Sub-agents must be explicit and bounded.** Clear role, scope, model policy, and capability surface.

## 5. Bounded Contexts

### 5.1 Task Orchestration Context
**Purpose:** Owns task intake, run lifecycle, checkpoints, status transitions, retries, cancellation, and completion.

**Primary concepts:**
- Task
- Run
- Objective
- Constraints
- SuccessCriteria
- TaskPlan
- TaskCheckpoint
- ApprovalRequest
- RunStatus

**Responsibilities:**
- accept task submissions
- normalize task contracts
- create and track run state
- coordinate long-running execution
- emit lifecycle events

### 5.2 Agent Runtime Context
**Purpose:** Owns DeepAgent construction, sub-agent registry, tool composition, middleware chain, skill loading, and turn execution.

**Primary concepts:**
- AgentHarness
- AgentSession
- SubAgent
- Skill
- Middleware
- ModelRoute
- RuntimeInvocation

**Responsibilities:**
- build primary DeepAgent
- register sub-agents
- resolve model assignments
- inject identity and policy
- coordinate agent turns against runtime ports

### 5.3 Execution Sandbox Context
**Purpose:** Owns filesystem exposure, shell/command execution, environment seeding, artifact capture, and isolation boundaries.

**Primary concepts:**
- ExecutionSandbox
- WorkspaceRoot
- ScratchSpace
- MemorySpace
- CommandRequest
- CommandResult
- SandboxPolicy
- ArtifactCapture

**Responsibilities:**
- provide the agent with a controlled working environment
- expose rooted file operations
- execute commands under policy
- capture outputs as artifacts
- prevent unsafe or uncontrolled host access

### 5.4 Memory Context
**Purpose:** Owns thread memory, durable memory, episodic summaries, project facts, and retrieval rules.

**Primary concepts:**
- RunMemory
- ProjectMemory
- IdentityMemory
- MemoryEntry
- MemorySummary
- RetrievalPolicy
- MemoryScope

**Responsibilities:**
- store run-local working knowledge
- persist selected durable knowledge
- retrieve memory for future tasks
- govern which memory types are promotable to durable state

### 5.5 Identity & Policy Context
**Purpose:** Owns the operating identity, principles, approvals, guardrails, action constraints, and escalation rules.

**Primary concepts:**
- IdentityBundle
- Principle
- PolicyRule
- CapabilityPolicy
- ApprovalPolicy
- EscalationRule

**Responsibilities:**
- load and version `IDENTITY.md`
- compile runtime identity prompts and policies
- define what actions require approval
- constrain tools and capabilities per task/run

### 5.6 Client Interaction Context
**Purpose:** Owns the runtime protocol, event stream contract, interaction affordances, and rendering-ready state.

**Primary concepts:**
- Session
- Command
- EventEnvelope
- ActionDescriptor
- ArtifactReference
- TaskSnapshot

**Responsibilities:**
- define client/runtime RPC methods
- define streaming event payloads
- express available follow-up actions
- enable progressive enhancement across CLI and future clients

### 5.7 Observability Context
**Purpose:** Owns structured logs, event correlation, traces, metrics, and diagnostics.

**Primary concepts:**
- CorrelationId
- RunTrace
- RuntimeMetric
- EventLog
- DiagnosticRecord

**Responsibilities:**
- tie all execution to run/task correlation IDs
- expose diagnostics for failures and loops
- enable replay and debugging

## 6. Context Relationships

- **Task Orchestration** invokes **Agent Runtime** to execute task work.
- **Agent Runtime** uses **Execution Sandbox**, **Memory**, and **Identity & Policy**.
- **Client Interaction** reads from **Task Orchestration** and **Observability**.
- **Observability** passively receives events from all contexts.
- **Identity & Policy** constrains **Task Orchestration**, **Agent Runtime**, and **Execution Sandbox**.

## 7. Clean Architecture Layers

### 7.1 Domain Layer
Contains the core business concepts and rules:
- task lifecycle
- policies
- identity model
- memory types and scopes
- artifact semantics
- client-visible action semantics

### 7.2 Application Layer
Contains use cases and orchestration:
- submit task
- start run
- resume run
- request approval
- stream events
- list artifacts
- inspect task state

### 7.3 Interface Layer
Contains transport and presentation adapters:
- JSON-RPC handlers
- CLI presenters
- future WebSocket/HTTP adapters
- serialization/deserialization

### 7.4 Infrastructure Layer
Contains framework and vendor integrations:
- LangChain DeepAgent adapter
- filesystem backend adapters
- sandbox adapters
- persistence stores
- telemetry emitters
- model provider integrations

## 8. Monorepo Structure

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

## 9. Runtime Ports and Adapters

The core runtime must depend on stable internal interfaces rather than directly on LangChain types.

### 9.1 Core Ports

```text
AgentHarness
TaskRunner
MemoryStore
ExecutionSandbox
ArtifactStore
ModelResolver
PolicyEngine
EventBus
CheckpointStore
SkillRegistry
SubAgentRegistry
```

### 9.2 Required Adapter Implementations

- `LangChainDeepAgentHarness`
- `FileSystemSandboxAdapter`
- `CommandExecutionAdapter`
- `StoreBackedMemoryAdapter`
- `JsonRpcTransportAdapter`
- `StdIoServerAdapter`
- `SseOrWebSocketAdapter` (future)

## 10. DeepAgent Integration Strategy

The runtime will host a Python composition root that builds a primary DeepAgent and a set of specialized sub-agents. The runtime is responsible for:

- loading the active identity bundle
- resolving model configuration for the primary agent and each sub-agent
- injecting approved tools and skills
- attaching memory and sandbox adapters
- wiring middleware for observability, policy enforcement, and approval interception

### 10.1 Explicit Sub-Agent Roles

#### Planner
Breaks objectives into milestones, execution steps, and checkpoints.

#### Researcher
Gathers facts, reads documentation, identifies constraints, and summarizes findings.

#### Coder
Creates and modifies code and structured artifacts inside the workspace.

#### Verifier
Runs checks, validates outputs, and evaluates acceptance criteria.

#### Librarian
Curates memory, retrieves prior facts, and promotes durable knowledge when policy allows.

### 10.2 Sub-Agent Design Rules

Each sub-agent must define:
- role description
- allowed tools
- file scope
- memory scope
- model route
- escalation behavior
- artifact expectations

Sub-agents must not share a single unconstrained capability pool.

## 11. Memory Model

### 11.1 Memory Types

#### Run Memory
Ephemeral or durable execution context tied to a single run.
Examples:
- current plan
- recent findings
- temporary summaries
- pending assumptions

#### Project Memory
Durable facts and conventions associated with a project/workspace.
Examples:
- coding conventions
- repo structure notes
- recurring domain facts
- preferred build/test commands

#### Identity Memory
Controlled operating guidance derived from `IDENTITY.md` and policy files.
Examples:
- principles
- tone and behavior constraints
- escalation rules
- autonomy boundaries

### 11.2 Rules

- not all memory can become durable
- identity memory is controlled, not agent-authored by default
- run memory promotion into project memory requires explicit policy
- memory retrieval must be scoped and explainable

## 12. Execution Sandbox Model

The runtime must provide a governed execution environment built from distinct logical zones.

### 12.1 Zones

#### Workspace Zone
The primary rooted filesystem available for task work.

#### Scratch Zone
Ephemeral space for temporary files, command outputs, and non-durable intermediate work.

#### Memory Zone
Controlled storage area for durable agent-authored notes and structured memory records.

### 12.2 Sandbox Policies

- all paths are rooted under runtime-managed directories
- host filesystem access outside mounted roots is denied
- command execution is mediated by policy
- environment variables are allowlisted
- artifact outputs are captured and registered
- execution should be observable and replay-friendly

## 13. Configuration Model

Configuration must support model routing, tool enablement, runtime paths, transport behavior, and approval policy.

### 13.1 Example

```toml
[runtime]
workspace_root = "./workspace"
transport = "stdio"
event_buffer_size = 500

[identity]
path = "./agents/primary-agent/IDENTITY.md"

[models.default]
provider = "openai"
model = "gpt-5"

[models.primary_agent]
provider = "anthropic"
model = "claude-sonnet-4-5"

[models.subagents.planner]
provider = "openai"
model = "gpt-5-mini"

[models.subagents.researcher]
provider = "openai"
model = "gpt-5-mini"

[models.subagents.coder]
provider = "openai"
model = "gpt-5"

[models.subagents.verifier]
provider = "anthropic"
model = "claude-sonnet-4-5"

[policy]
approval_mode = "on-dangerous-actions"
allow_shell = true
allow_network = false
```

### 13.2 Configuration Principles

- defaults should be explicit
- sub-agent overrides are first-class
- transport selection is externalized
- policy should be configurable without changing client code

## 14. Task Contract

Every task submitted to the runtime must be normalized into a structured task contract.

### 14.1 Required Fields

- objective
- scope
- constraints
- success criteria
- allowed capabilities
- workspace roots
- approval policy
- identity bundle version

### 14.2 Optional Fields

- deadline or urgency
- artifact expectations
- preferred sub-agents
- retry policy
- checkpoint frequency

### 14.3 Example

```json
{
  "objective": "Implement a parser for config format X",
  "scope": "Repository workspace only",
  "constraints": [
    "Do not modify CI configuration",
    "Do not access network"
  ],
  "success_criteria": [
    "Parser handles required grammar",
    "Tests are added and pass",
    "CLI usage is documented"
  ],
  "allowed_capabilities": [
    "read_files",
    "write_files",
    "execute_commands"
  ],
  "workspace_roots": ["/workspace/project"],
  "approval_policy": "on-dangerous-actions",
  "identity_bundle_version": "v1"
}
```

## 15. Protocol Recommendation

### 15.1 Initial Transport
Use **JSON-RPC 2.0 over stdio** for the first CLI/runtime integration.

### 15.2 Future Transports
Support the same conceptual contract over:
- WebSocket
- HTTP + SSE

### 15.3 Why This Approach

- simple local startup
- no forced server-first architecture
- easy CLI integration
- naturally extensible to future clients
- compatible with event streaming and long-running task execution

## 16. Protocol Contract

### 16.1 Core RPC Methods

- `task.submit`
- `task.status`
- `task.cancel`
- `task.resume`
- `task.logs`
- `task.artifacts`
- `task.approval.respond`
- `memory.inspect`
- `config.doctor`
- `runtime.health`

### 16.2 Streaming Events

Clients should subscribe to runtime events for task progress and state transitions.

#### Event Types
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

### 16.3 Event Envelope

```json
{
  "event_id": "evt_123",
  "event_type": "plan.updated",
  "task_id": "task_456",
  "run_id": "run_789",
  "timestamp": "2026-03-10T18:30:00Z",
  "correlation_id": "corr_001",
  "payload": {}
}
```

### 16.4 HATEOAS-Inspired Action Descriptors

Task snapshots should include available actions so that clients render affordances without embedding orchestration rules.

Example:

```json
{
  "task_id": "task_456",
  "status": "awaiting_approval",
  "actions": [
    {
      "name": "approve_shell_execution",
      "method": "task.approval.respond",
      "input_schema": {
        "type": "object",
        "required": ["approval_id", "decision"]
      }
    },
    {
      "name": "cancel_task",
      "method": "task.cancel",
      "input_schema": {
        "type": "object",
        "required": ["task_id"]
      }
    }
  ]
}
```

## 17. CLI Scope

The initial CLI should be intentionally thin.

### 17.1 Initial Command Surface

```bash
agent task run "Implement a parser for X"
agent task status <task-id>
agent task logs <task-id>
agent task artifacts <task-id>
agent task approve <task-id> <action>
agent memory inspect
agent config doctor
```

### 17.2 CLI Responsibilities

- collect user intent
- call runtime protocol methods
- render event streams and task snapshots
- display artifacts and approvals

### 17.3 CLI Non-Responsibilities

- task orchestration
- memory policy
- planning logic
- tool routing
- sandbox decisions

## 18. Observability Requirements

The system must support:

- structured logs with task/run correlation IDs
- durable runtime events
- command execution traces
- sub-agent invocation traces
- task replay and debugging support
- metrics for completion, failure, retries, and approval frequency

## 19. Security and Safety Requirements

- runtime access must be explicitly bounded by policy
- dangerous capabilities must be interceptable for approval
- environment leakage must be minimized
- identity and policy versions must be traceable per run
- network access should be off by default unless explicitly enabled
- artifact export must be distinct from agent filesystem tooling

## 20. Architectural Risks

### 20.1 CLI Accretion
Risk that orchestration logic leaks into the CLI.

**Mitigation:** keep protocol rich and CLI thin.

### 20.2 Framework Leakage
Risk that LangChain concepts become the domain model.

**Mitigation:** enforce internal ports and adapters.

### 20.3 Unbounded Sandbox Access
Risk that the agent gains uncontrolled host access.

**Mitigation:** rooted workspaces, mediated execution, allowlisted environment.

### 20.4 Memory Sprawl
Risk that all state becomes undifferentiated durable memory.

**Mitigation:** typed memory model with promotion rules.

### 20.5 Sub-Agent Capability Bleed
Risk that every sub-agent can do everything.

**Mitigation:** explicit per-agent tool, scope, and model policy.

## 21. Recommended ADRs

The following Architecture Decision Records should be created next:

1. **ADR-001: Transport Strategy for Local Client/Runtime Communication**
2. **ADR-002: DeepAgent Adapter Boundary and LangChain Isolation**
3. **ADR-003: Memory Taxonomy and Promotion Rules**
4. **ADR-004: Execution Sandbox Rooting and Command Policy**
5. **ADR-005: Sub-Agent Registry and Model Routing Strategy**

## 22. Initial Delivery Recommendation

Build the system in this order:

1. monorepo skeleton
2. protocol package and task model
3. runtime shell with health/config APIs
4. task submission and event streaming
5. single-agent DeepAgent adapter
6. filesystem sandbox and command execution
7. durable memory and checkpoints
8. sub-agent registry and model routing
9. artifact browsing and richer clients

## 23. Summary

The central design choice is to treat the Python DeepAgent host as a **dedicated runtime platform** rather than a library called directly by the CLI. That separation gives the project room to grow into a multi-client system, keeps autonomy bounded by explicit identity and policy, and aligns strongly with the Triadic Lens.

The runtime should own task orchestration, memory, sandboxes, model routing, identity, and eventing. The CLI should remain a clean client over a stable runtime protocol. LangChain DeepAgent should be used through carefully bounded adapters so that the product's architecture remains coherent even as implementation details evolve.
