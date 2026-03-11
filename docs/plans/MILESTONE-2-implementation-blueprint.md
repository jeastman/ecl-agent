## Local Agent Harness — Durable Runtime, Memory, and Approval Governance

**Status:** Draft
**Date:** 2026-03-10
**Audience:** Runtime engineers, CLI engineers, AI coding agents
**Purpose:** Concrete implementation blueprint for delivering Milestone 2

---

# 1. Blueprint Intent

This blueprint translates `MILESTONE-2.md` into an implementation-ready plan.

It defines:

- concrete package responsibilities
- interface shapes for Milestone 2 subsystems
- LangGraph-compatible checkpoint integration
- lightweight approval and policy flow
- durable memory design
- runtime protocol extensions
- CLI command behavior
- test and rollout order

This document is intentionally practical. It should be usable as a build map for human developers and AI coding agents.

---

# 2. Milestone 2 Outcome

At the end of Milestone 2, the runtime should support:

1. durable project memory
2. persisted event history
3. approval-aware task execution
4. policy decisions around risky operations
5. checkpoint-backed pause/resume
6. recovery from runtime restart
7. inspection of memory and effective config

Milestone 2 should make the runtime **durable, resumable, governed, and inspectable** without yet introducing full sub-agent orchestration.

---

# 3. Build Order

Implement Milestone 2 in this order:

1. **Persistent stores foundation**
2. **CheckpointStore port + LangGraph adapter**
3. **MemoryStore + memory record model**
4. **PolicyEngine + approval model**
5. **Persistent EventStore + diagnostics**
6. **TaskRunner pause/resume lifecycle**
7. **Runtime protocol extensions**
8. **CLI command extensions**
9. **Crash/restart recovery validation**
10. **Acceptance testing**

This order ensures the runtime becomes durable before governance behavior is layered on top.

---

# 4. Package Responsibility Map

## 4.1 `apps/runtime`
Add or update:
- `bootstrap.py`
- `runtime_server.py`
- `method_handlers.py`
- `task_runner.py`
- `resume_service.py`
- `recovery_service.py`

Responsibilities:
- wire new persistent services
- expose new protocol methods
- coordinate pause/resume transitions
- recover active runs on startup

## 4.2 `apps/cli`
Add or update:
- `commands/approvals.py`
- `commands/approve.py`
- `commands/resume.py`
- `commands/memory.py`
- `commands/config.py`

Responsibilities:
- display approval requests
- submit approval decisions
- resume runs
- inspect memory
- inspect redacted config

## 4.3 `packages/protocol`
Add:
- approval request/decision models
- memory inspection models
- config inspection models
- task resume request/response models
- checkpoint metadata models
- persistent diagnostic models

Responsibilities:
- stable shared contracts
- typed request/response payloads
- event payload schemas for approval and resumption

## 4.4 `services/deepagent-runtime`
Add or update:
- `deepagent_harness.py`
- `checkpoint_adapter.py`
- `interrupt_bridge.py`

Responsibilities:
- connect runtime checkpoint semantics to LangGraph-compatible checkpointing
- pause/resume through framework-compatible flows
- keep LangGraph specifics out of runtime-facing interfaces

## 4.5 `services/memory-service`
Add:
- `memory_store.py`
- `memory_models.py`
- `memory_promotion.py`

Responsibilities:
- durable project memory persistence
- memory scope handling
- provenance-aware records
- promotion from run/scratch memory into project memory

## 4.6 `services/policy-service`
Add:
- `policy_engine.py`
- `approval_store.py`
- `policy_models.py`
- `boundary_scope.py`

Responsibilities:
- classify operations
- decide allow / require approval / deny
- create and track approval requests
- cache run-scoped grants

## 4.7 `services/observability-service`
Add:
- `event_store.py`
- `diagnostic_store.py`
- `run_metrics_store.py`

Responsibilities:
- persist events
- persist diagnostics
- track checkpoint and approval metrics

## 4.8 `services/checkpoint-service`
Add:
- `checkpoint_store.py`
- `checkpoint_models.py`
- `thread_registry.py`

Responsibilities:
- runtime-facing checkpoint port
- LangGraph-compatible adapter
- mapping of task/run to thread_id
- checkpoint metadata lookup

---

# 5. Milestone 2 Runtime Interfaces

These ports should exist before adapters are implemented.

## 5.1 `CheckpointStore`

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class CheckpointMetadata:
    checkpoint_id: str
    task_id: str
    run_id: str
    thread_id: str
    checkpoint_index: int
    created_at: str
    reason: str | None = None

@dataclass
class ResumeHandle:
    task_id: str
    run_id: str
    thread_id: str
    latest_checkpoint_id: str | None

class CheckpointStore(Protocol):
    def create_thread(self, task_id: str, run_id: str) -> str:
        ...

    def save_metadata(self, metadata: CheckpointMetadata) -> None:
        ...

    def list_checkpoints(self, task_id: str, run_id: str) -> list[CheckpointMetadata]:
        ...

    def get_resume_handle(self, task_id: str, run_id: str) -> ResumeHandle | None:
        ...

    def bind_runtime_thread(self, task_id: str, run_id: str, thread_id: str) -> None:
        ...
```

### Design notes

- checkpoint payloads remain framework-native
- this interface manages metadata, thread binding, and lookup
- LangGraph persistence remains inside the adapter

## 5.2 MemoryStore
```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class MemoryRecord:
    memory_id: str
    scope: str
    namespace: str
    content: str
    summary: str
    provenance: dict
    created_at: str
    updated_at: str
    source_run: str | None = None
    confidence: float | None = None

class MemoryStore(Protocol):
    def write_memory(self, record: MemoryRecord) -> None:
        ...

    def read_memory(self, memory_id: str) -> MemoryRecord | None:
        ...

    def list_memory(
        self,
        scope: str | None = None,
        namespace: str | None = None,
    ) -> list[MemoryRecord]:
        ...

    def delete_memory(self, memory_id: str) -> None:
        ...
```

## 5.3 PolicyEngine

```python
from dataclasses import dataclass
from typing import Protocol, Literal

PolicyDecisionKind = Literal["ALLOW", "REQUIRE_APPROVAL", "DENY"]

@dataclass
class OperationContext:
    task_id: str
    run_id: str
    operation_type: str
    path_scope: str | None = None
    command_class: str | None = None
    memory_scope: str | None = None
    namespace: str | None = None
    agent_role: str | None = None
    metadata: dict | None = None

@dataclass
class PolicyDecision:
    decision: PolicyDecisionKind
    reason: str
    boundary_key: str | None = None
    approval_scope: dict | None = None

class PolicyEngine(Protocol):
    def evaluate(self, context: OperationContext) -> PolicyDecision:
        ...
```
## 5.4 ApprovalStore

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class ApprovalRequest:
    approval_id: str
    task_id: str
    run_id: str
    type: str
    scope: dict
    description: str
    created_at: str
    status: str
    decision: str | None = None
    decided_at: str | None = None

class ApprovalStore(Protocol):
    def create_request(self, request: ApprovalRequest) -> None:
        ...

    def get_request(self, approval_id: str) -> ApprovalRequest | None:
        ...

    def list_for_task(self, task_id: str, run_id: str | None = None) -> list[ApprovalRequest]:
        ...

    def decide(self, approval_id: str, decision: str, decided_at: str) -> ApprovalRequest:
        ...
```

## 5.5 EventStore

```python
from typing import Protocol

class EventStore(Protocol):
    def append_event(self, event: dict) -> None:
        ...

    def get_events(
        self,
        task_id: str,
        run_id: str | None = None,
        from_event_id: str | None = None,
    ) -> list[dict]:
        ...
```

## 5.6 DiagnosticStore

```python
from typing import Protocol

class DiagnosticStore(Protocol):
    def append_diagnostic(self, record: dict) -> None:
        ...

    def list_diagnostics(
        self,
        task_id: str,
        run_id: str | None = None,
    ) -> list[dict]:
        ...
```

# 6. LangGraph-Compatible Checkpoint Blueprint
## 6.1 Design rule

Do not replace LangGraph checkpoint semantics with a custom checkpoint payload format.

Instead:
- the runtime owns a CheckpointStore port
- the adapter implements it with a LangGraph-compatible checkpointer
- the runtime stores metadata beside framework-native checkpoints

## 6.2 Adapter shape

File: `services/deepagent-runtime/checkpoint_adapter.py`

```python
class LangGraphCheckpointStore(CheckpointStore):
    def __init__(self, checkpointer, thread_registry, metadata_store) -> None:
        ...
```

Responsibilities:

- create or bind thread_id
- attach thread_id to agent execution config
- record checkpoint metadata at super-step boundaries or interrupt points
- expose resume handles to the runtime

## 6.3 Thread registry

File: `services/checkpoint-service/thread_registry.py`

Responsibilities:
- map task_id + run_id -> thread_id
- persist the mapping
- support lookup after restart

Suggested storage:
- local SQLite or simple file-backed store for Milestone 2

## 6.4 Resume behavior

The runtime should resume by:
1. looking up thread_id from the registry
2. rebuilding the agent harness
3. passing the same thread_id back into execution config
4. continuing from the latest framework-native checkpoint

The runtime must not attempt to reconstruct internal agent graph state itself.

# 7. Durable Memory Blueprint
## 7.1 Storage model

For Milestone 2, use a simple durable local store:

- SQLite
- or structured JSONL/JSON file-backed store if SQLite is not yet desired

SQLite is recommended because:
- it supports query by scope/namespace
- it supports durable restart behavior
- it can later support memory inspection commands cleanly

## 7.2 Memory scopes

Support these scopes:
- run
- project
- identity
- scratch

Rules:
- identity is controlled input, not general freeform writes
- project is durable and queryable across runs
- run may persist for inspection/recovery but is not the same as project memory
- scratch is ephemeral by policy

## 7.3 Memory promotion flow

The agent should not directly persist arbitrary project memory.

Instead:
1. the agent proposes a memory write
2. the runtime classifies the proposal
3. policy decides:
  - allow
  - require approval
  - deny
4. if allowed, the runtime writes/promotes the record

## 7.4 Provenance model

Every durable memory record should include provenance such as:
- source task_id
- source run_id
- source role
- triggering artifact or file path
- promotion reason

# 8. Approval and Policy Blueprint
## 8.1 Approval philosophy

Approvals should be boundary-based, not operation-based.

The runtime should avoid asking:
- once per file write
- once per command
- once per memory record

The runtime should instead ask for a scoped boundary grant such as:
- allow writes to apps/runtime/** for this run
- allow test/build commands in workspace root for this run
- allow durable memory writes in namespace project.conventions

## 8.2 Default policy tiers
### Auto-Allow
Examples:
- reading inside declared workspace
- writing under artifacts/
- writing to scratch
- safe read-only command classes
- in-scope run memory updates

### Require Approval

Examples:
- first write to a new protected subtree
- first execution of non-safe command class
- first durable project memory write in a namespace
- scope expansion beyond original task area

### Deny

Examples:
- writes outside configured workspace roots
- destructive command classes
- secret access
- external network access
- mutation of protected identity inputs

## 8.3 Run-scoped grant cache

Approval decisions should be cached for the run by boundary_key.

This prevents repeated prompts for the same scope.

File: services/policy-service/boundary_scope.py

Responsibilities:
- compute stable boundary keys
- check existing granted boundaries
- record newly granted boundaries

## 8.4 Interrupt bridge

File: `services/deepagent-runtime/interrupt_bridge.py`

Responsibilities:
- translate policy-required approval pauses into framework-compatible interrupt behavior
- surface an `approval.requested` event
- return control to runtime without losing resumability

# 9. TaskRunner Milestone 2 Changes

TaskRunner must evolve from simple execution orchestration into lifecycle management for:
- approvals
- checkpoints
- resumption
- durable observability
- memory promotion

## 9.1 New responsibilities

- create `thread_id` for new runs
- persist event history via EventStore
- create approval requests when policy requires
- transition run state to awaiting_approval
- resume from checkpoint after approval or restart
- persist diagnostics and metrics

## 9.2 Suggested new methods

```python
class TaskRunner:
    def start_run(...):
        ...

    def resume_run(self, task_id: str, run_id: str) -> dict:
        ...

    def approve(self, approval_id: str, decision: str) -> dict:
        ...

    def inspect_memory(self, scope: str | None = None, namespace: str | None = None) -> list[dict]:
        ...

    def get_effective_config(self) -> dict:
        ...
```
## 9.3 Pause flow
- tool or operation request is evaluated by `PolicyEngine`
- decision is `REQUIRE_APPROVAL`
- approval request is created
- event `approval.requested` is persisted/emitted
- run state becomes `awaiting_approval`
- execution pauses using checkpoint-compatible behavior

## 9.4 Resume flow after approval
- CLI calls `task.approve`
- runtime records decision
- if approved, runtime grants boundary for run
- runtime calls `resume_run`
- latest checkpoint/thread_id is loaded
- execution continues
- event `task.resumed` is emitted

# 10. Persistent Observability Blueprint
## 10.1 Event persistence

Milestone 1 used an in-memory event bus. Milestone 2 should persist event history.

Recommended first implementation:
- keep an in-memory pub/sub bus for live streaming
- also append every event to EventStore

This gives:
- live UX
- durable replay

## 10.2 Diagnostics

Diagnostics should be stored for:
- policy denials
- sandbox violations
- checkpoint/resume failures
- agent execution errors

Suggested diagnostic fields:
- diagnostic_id
- task_id
- run_id
- category
- message
- details
- created_at

## 10.3 Run metrics

Track:
- start/end timestamps
- approval count
- checkpoint count
- event count
- artifact count
- resume count
- deny count

These do not need a complex analytics engine in Milestone 2; a simple per-run metrics record is enough.

# 11. Runtime Protocol Extension Blueprint
## 11.1 New methods

Implement:
- `task.approve`
- `task.resume`
- `memory.inspect`
- `config.get`

Optional if useful:
- `task.approvals.list`

## 11.2 New events

Implement:
- `approval.requested`
- `task.paused`
- `task.resumed`
- `memory.updated`
- `policy.denied` (optional but useful)

## 11.3 Request/response guidance

### `task.approve`

Params:
- `task_id`
- `run_id`
- `approval`

Result:
- `approval_id`
- `accepted`
- `status`

### `task.resume`

Params:
- `task_id`
- `run_id`

Result:
- `task_id`
- `run_id`
- `status`

### `memory.inspect`

Params:
- optional `scope`
- optional `namespace`

Result:
- `entries`
- `count`

### config.get

Result:
- effective config
- loaded profiles
- redaction metadata

# 12. CLI Blueprint
## 12.1 Commands

Implement:
```bash
agent approvals <task_id>
agent approve <approval_id> --decision approve
agent resume <task_id>
agent memory --scope project
agent config
```

## 12.2 Rendering guidance
### `agent approvals`

Show:
- approval id
- status
- type
- scope summary
- description
- created_at

### `agent approve`

Show:
- approval id
- decision accepted
- run resumed or awaiting next action

### `agent memory`

Show:
- scope
- namespace
- summary
- provenance snippet
- created/updated timestamps

### agent config

Show redacted effective config, not raw secrets.

# 13. Persistence Technology Recommendation

Milestone 2 can use a pragmatic local persistence stack:

- SQLite for:
  - memory records
  - approval requests
  - thread registry
  - run metrics
  - diagnostics metadata

- File-backed or SQLite-backed storage for:
  - event records
  - checkpoint metadata

- LangGraph-compatible checkpointer backend for:
  - actual framework checkpoints

This keeps the milestone realistic while preserving future replaceability.

# 14. Testing Blueprint
## 14.1 Unit tests
### Checkpointing
- thread registry binds task/run to thread_id
- metadata is recorded per checkpoint
- resume handle lookup works

### Policy
- safe operations auto-allow
- scope expansion requires approval
- dangerous operations deny

### Approvals
- request create/read/list/decide works
- run-scoped grant cache suppresses duplicate prompts

### Memory
- durable write/read/list works
- promotion preserves provenance
- denied promotion does not persist

## 14.2 Integration tests
### Pause/resume
- task triggers approval
- task enters awaiting_approval
- approval is granted
- task resumes and completes

### Restart recovery
- task reaches checkpoint
- runtime stops
- runtime restarts
- task can be resumed from stored thread_id

### Memory inspection
- project memory written
- memory.inspect returns expected entries

### Config inspection
- config.get returns effective config with redactions

## 14.3 End-to-end scenario

Use a task that:
1. reads repo files
2. proposes a durable project memory entry
3. triggers one boundary approval
4. pauses
5. resumes
6. completes with artifact and memory update

This validates nearly the full Milestone 2 surface.

# 15. Suggested File Skeleton

```text
apps/
  runtime/
    bootstrap.py
    runtime_server.py
    method_handlers.py
    task_runner.py
    resume_service.py
    recovery_service.py

  cli/
    client.py
    commands/
      approvals.py
      approve.py
      resume.py
      memory.py
      config.py

services/
  deepagent-runtime/
    deepagent_harness.py
    checkpoint_adapter.py
    interrupt_bridge.py

  checkpoint-service/
    checkpoint_store.py
    checkpoint_models.py
    thread_registry.py

  memory-service/
    memory_store.py
    memory_models.py
    memory_promotion.py

  policy-service/
    policy_engine.py
    approval_store.py
    policy_models.py
    boundary_scope.py

  observability-service/
    event_store.py
    diagnostic_store.py
    run_metrics_store.py
```

# 16. Minimal Pseudocode Flows

## 16.1 Policy-gated operation

```python
decision = policy_engine.evaluate(
    OperationContext(
        task_id=task_id,
        run_id=run_id,
        operation_type="write_file",
        path_scope="apps/runtime/**",
    )
)

if decision.decision == "ALLOW":
    perform_operation()
elif decision.decision == "REQUIRE_APPROVAL":
    approval = approval_store.create_request(...)
    append_event("approval.requested", {"approval": approval})
    update_run_state(status="awaiting_approval")
    checkpoint_and_pause()
else:
    append_diagnostic(...)
    raise PolicyDeniedError(decision.reason)
```

## 16.2 Resume after approval

```python
approval = approval_store.decide(approval_id, "approve", decided_at=now())
grant_boundary_for_run(approval.scope)

resume_handle = checkpoint_store.get_resume_handle(task_id, run_id)
result = task_runner.resume_run(task_id, run_id)
```

## 16.3 Memory promotion

```python
proposal = MemoryRecord(
    memory_id=generate_id(),
    scope="project",
    namespace="project.conventions",
    content="Use runtime-owned protocol contracts for all client integrations.",
    summary="Protocol contracts are runtime-owned.",
    provenance={"task_id": task_id, "run_id": run_id},
    created_at=now(),
    updated_at=now(),
)

decision = policy_engine.evaluate(
    OperationContext(
        task_id=task_id,
        run_id=run_id,
        operation_type="promote_memory",
        memory_scope="project",
        namespace="project.conventions",
    )
)

if decision.decision == "ALLOW":
    memory_store.write_memory(proposal)
    append_event("memory.updated", {"scope": "project", "summary": proposal.summary})
```

# 17. Anti-Patterns to Avoid

Do not:
- store custom checkpoint payloads instead of using LangGraph-compatible persistence
- merge project memory and checkpoint state into one store
- ask for approvals on every file or command
- let the CLI own approval or resume logic
- expose secrets through config.get
- leak LangGraph types into shared packages or protocol models

# 18. Exit Criteria

This blueprint is fulfilled when the codebase contains a Milestone 2 implementation that:
- supports LangGraph-compatible checkpoint-backed resumption
- persists durable project memory
- enforces a lightweight boundary-based approval workflow
- persists event history and diagnostics
- exposes task.approve, task.resume, memory.inspect, and config.get
- supports CLI inspection of approvals, memory, and resumed tasks
- preserves architecture boundaries from Milestones 0 and 1
