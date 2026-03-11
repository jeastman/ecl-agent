# MILESTONE-2.md
## Local Agent Harness — Durable Runtime, Memory, and Approval Governance

**Status:** Planned
**Date:** 2026-03-10
**Milestone Theme:** Durable, Governed, and Resumable Agent Runtime

---

# 1. Milestone Objective

Milestone 2 evolves the Local Agent Harness from a **working execution runtime** into a **durable and governed agent platform**.

Milestone 1 proved that:

- CLI → Runtime → AgentHarness → Sandbox → Artifacts works
- The runtime can execute real tasks end-to-end

Milestone 2 adds the capabilities necessary for **long-running autonomous agents**:

- durable project memory
- checkpointing and resumability
- scoped approval workflow
- policy-driven runtime governance
- persistent observability and diagnostics
- runtime inspection APIs

The milestone must maintain the **Triadic Lens architectural discipline**:

- clear bounded contexts
- ports/adapters around external frameworks
- strong runtime ownership of orchestration

---

# 2. Design Principles

Milestone 2 is guided by five key principles.

## 2.1 DeepAgent Compatibility

Checkpointing must be **LangGraph compatible** so that the runtime works naturally with LangChain DeepAgents.

The runtime must **wrap** the LangGraph checkpointing mechanism rather than replacing it.

---

## 2.2 Autonomous Agents by Default

Agents should operate autonomously without constant human supervision.

Approvals must therefore be:

- **sparse**
- **high-signal**
- **boundary-based**

The system must never degrade into:

- excessive micro-approvals
- YOLO permission mode

---

## 2.3 Runtime as the Governance Layer

The runtime owns:

- policy enforcement
- approval orchestration
- memory promotion rules
- checkpoint lifecycle

The AgentHarness must remain unaware of governance internals.

---

## 2.4 Memory is Separate From Checkpoints

Checkpoint state represents **execution state**.

Project memory represents **long-term knowledge**.

They must remain separate stores.

---

## 2.5 Framework Isolation

LangChain / LangGraph must remain inside adapter layers.

No LangGraph types may leak into:

- protocol layer
- CLI
- core runtime interfaces

---

# 3. Milestone 2 Capability Overview

Milestone 2 introduces five new runtime subsystems.

| Capability | Description |
|---|---|
| Durable Memory | Persistent project knowledge store |
| Checkpoints | Resume execution after pause or restart |
| Approval Workflow | Lightweight human gating |
| Policy Engine | Runtime governance decisions |
| Observability | Persistent event and diagnostic data |

---

# 4. Checkpointing and Resumability

## 4.1 Goal

Enable tasks to:

- pause for approvals
- survive runtime restarts
- resume execution safely

---

## 4.2 Architecture

Introduce a new runtime port:
CheckpointStore

The primary adapter will be:
LangGraphCheckpointStore


This adapter wraps a **LangGraph checkpointer**.

---

## 4.3 Identifier Mapping

| Identifier | Purpose |
|---|---|
| task_id | logical task identity |
| run_id | execution attempt |
| thread_id | LangGraph checkpoint cursor |

The runtime maps:
task_id + run_id -> thread_id

---

## 4.4 Checkpoint Responsibilities

CheckpointStore must support:
create_thread()
save_checkpoint()
load_checkpoint()
list_checkpoints()
resume_from_checkpoint()

The **checkpoint payload itself remains LangGraph native**.

The runtime stores metadata alongside it.

---

## 4.5 Resume Flow

Resume occurs when:

- approval is granted
- runtime restarts
- user invokes resume command

Flow:

1. runtime loads checkpoint via thread_id
2. runtime restores run state
3. runtime re-invokes AgentHarness
4. execution continues

---

# 5. Durable Project Memory

## 5.1 Goal

Allow the agent to accumulate **long-term knowledge across tasks**.

Examples:

- coding conventions
- discovered architecture patterns
- learned project insights

---

## 5.2 Memory Scopes

Memory must support multiple scopes.

| Scope | Persistence |
|---|---|
| run | temporary |
| project | durable |
| identity | doctrine |
| scratch | ephemeral |

---

## 5.3 Memory Record Model

Each memory record must contain:
memory_id
scope
namespace
content
summary
provenance
created_at
updated_at
source_run
confidence

---

## 5.4 MemoryStore Interface

MemoryStore

write_memory()
read_memory()
list_memory()
promote_memory()
delete_memory()


---

## 5.5 Memory Promotion

Agents should not freely write durable memory.

Instead:

1. agent proposes memory
2. policy engine evaluates
3. memory is promoted to project scope

---

# 6. Approval Workflow

Milestone 2 introduces a **lightweight boundary-based approval model**.

---

# 6.1 Approval Philosophy

Approvals must be:

- rare
- meaningful
- scoped

Avoid approval spam.

---

# 6.2 Approval Types

Three approval levels exist.

### Auto-Allow

Low-risk operations allowed automatically.

Examples:

- reading workspace files
- writing artifacts
- scratch file writes

---

### Boundary Approval

Triggered when agent expands scope.

Examples:

- writing to new directories
- executing non-safe commands
- creating new durable memory namespace

Approval grants permission for the **entire boundary**.

Example:

"Allow writes to apps/runtime/** for this run"

---

### Hard Stop Approval

Always requires explicit user consent.

Examples:

- external network access
- destructive commands
- secrets access

---

# 6.3 Approval Request Model

ApprovalRequest

approval_id
task_id
run_id
type
scope
description
created_at
status
decision
decided_at


---

# 6.4 Approval Lifecycle

pending -> approved
pending -> rejected


When pending:
run_state = awaiting_approval


Execution resumes once approved.

---

# 7. Policy Engine

## 7.1 Goal

Provide runtime-level governance decisions.

The PolicyEngine decides:

- whether to auto-allow
- whether approval is required
- whether to reject the action

---

## 7.2 Policy Inputs

Policies evaluate:
operation_type
path_scope
command_class
memory_scope
agent_role
runtime_config

---

## 7.3 Policy Outputs

Policy decisions:
ALLOW
REQUIRE_APPROVAL
DENY


---

# 8. Observability Improvements

Milestone 2 upgrades runtime observability.

---

## 8.1 Persistent Event Log

Events must persist beyond runtime restart.

EventStore should support:
append_event()
get_events()
stream_events()


---

## 8.2 Run Metrics

Track metrics such as:
run_duration
artifact_count
approval_count
checkpoint_count
policy_decisions


---

## 8.3 Diagnostics

Capture structured diagnostic data when:

- policy denies action
- sandbox blocks access
- agent errors occur

---

# 9. Protocol Extensions

Milestone 2 introduces new protocol methods.

---

## 9.1 task.approve

Approve a pending action.

---

## 9.2 task.resume

Resume paused task.

---

## 9.3 memory.inspect

View runtime memory state.

---

## 9.4 config.get

Retrieve effective runtime configuration.

Sensitive values must be redacted.

---

# 10. CLI Enhancements

CLI gains new commands.
agent approvals <task_id>
agent approve <approval_id>
agent resume <task_id>
agent memory
agent config


---

# 11. Testing Requirements

Milestone 2 must include:

### Unit Tests

- checkpoint lifecycle
- policy evaluation
- approval lifecycle
- memory promotion

### Integration Tests

- pause/resume execution
- approval gating behavior
- memory persistence

### Fault Recovery

Simulate runtime crash and confirm resume.

---

# 12. Milestone Acceptance Criteria

Milestone 2 is complete when:

- durable memory store exists
- memory.inspect works
- checkpoint store integrated with DeepAgent
- tasks survive runtime restart
- approval workflow works end-to-end
- policy engine governs runtime actions
- event history persists
- CLI can inspect approvals and memory
- runtime/client separation preserved

---

# 13. Out of Scope

Milestone 2 does NOT introduce:

- sub-agent orchestration
- role-based model routing
- skills system
- remote sandboxes
- web UI

These belong to **Milestone 3**.

---

# 14. Milestone Outcome

At the end of Milestone 2 the runtime becomes:

**Durable**
**Governed**
**Resumable**
**Inspectable**

The system will be capable of supporting **long-running autonomous tasks safely**.

---

# 15. Next Milestone Preview

Milestone 3 will introduce:

- sub-agent registry
- planner / researcher / coder / verifier roles
- model routing policies
- skills subsystem
