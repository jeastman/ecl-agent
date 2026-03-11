
# MILESTONE-1.md
## Local Agent Harness — Milestone 1 Specification
**Milestone Name:** Single-Agent Runtime Vertical Slice  
**Status:** Planned  
**Target Outcome:** A working end‑to‑end execution path from CLI → runtime → agent harness → sandbox → artifacts → CLI

---

# 1. Milestone Objective

Milestone 1 transforms the repository from a **bootstrapped architecture** into a **working agent harness** capable of executing real tasks.

This milestone proves that the architecture defined in:

- Master Architecture Spec
- Runtime Protocol Spec
- ADR Pack

works **in practice**.

The milestone must produce a **complete vertical slice** of functionality:

CLI → Runtime → Agent Harness → Sandbox → Event Stream → Artifacts → CLI

The milestone intentionally implements **only a single agent configuration** and **run‑local memory**.

More advanced capabilities (durable memory, approvals, sub‑agent orchestration) are deferred to later milestones.

---

# 2. Definition of Done

Milestone 1 is complete when:

1. A CLI command can submit a task to the runtime.
2. The runtime creates a `task_id` and `run_id`.
3. The runtime invokes a **real AgentHarness implementation**.
4. The agent executes work using the sandbox backend.
5. Events stream back to the CLI during execution.
6. The agent can read/write files within the governed workspace.
7. The runtime registers artifacts created during execution.
8. The CLI can list artifacts associated with the task.
9. `task.get` returns the real task state.
10. The runtime architecture still respects:
    - runtime/client separation
    - adapter boundary for DeepAgent
    - sandbox mediation
    - protocol contract.

---

# 3. Scope

Milestone 1 **includes**:

- DeepAgent adapter implementation
- runtime task execution pipeline
- local sandbox implementation
- event streaming
- artifact capture
- run-local memory/state
- CLI inspection commands

Milestone 1 **does not include**:

- durable project memory
- approval workflows
- multi‑subagent orchestration
- remote sandbox support
- resumable runs across runtime restarts
- web UI

---

# 4. Architectural Focus

Milestone 1 validates these core architectural principles:

### Runtime is authoritative
All task lifecycle logic lives in the runtime.

### CLI is a thin client
The CLI cannot implement orchestration logic.

### DeepAgent isolation
LangChain / DeepAgent implementation must remain inside the adapter layer.

### Sandbox mediation
All filesystem and command access flows through the sandbox interface.

### Protocol correctness
All interactions must conform to the runtime protocol spec.

---

# 5. Vertical Execution Flow

The complete Milestone 1 flow:

1. CLI submits task via `task.create`
2. Runtime creates task + run
3. Runtime emits `task.created`
4. Runtime starts execution
5. Runtime invokes `AgentHarness`
6. Agent performs operations through sandbox tools
7. Runtime emits progress events
8. Artifacts are registered when created
9. Agent completes execution
10. Runtime emits `task.completed`
11. CLI displays results

---

# 6. Required Runtime Components

Milestone 1 requires concrete implementations of the following runtime interfaces.

## 6.1 AgentHarness

Responsible for invoking the agent execution.

Responsibilities:

- initialize the DeepAgent
- inject IDENTITY prompt context
- bind tools
- manage streaming callbacks
- return execution results

Initial implementation:

LangChainDeepAgentHarness

The adapter must translate between:

runtime concepts → DeepAgent configuration

---

## 6.2 TaskRunner

Coordinates execution of a task.

Responsibilities:

- create run context
- invoke AgentHarness
- publish events
- register artifacts
- update run state

Key methods:

start_run()
publish_event()
register_artifact()
complete_run()
fail_run()

---

## 6.3 ExecutionSandbox

Provides controlled filesystem and command access.

Responsibilities:

- workspace root isolation
- scratch space creation
- command execution
- path normalization
- artifact detection

Initial zones:

workspace/
scratch/
memory/

---

## 6.4 ArtifactStore

Registers outputs created during execution.

Responsibilities:

- assign artifact_id
- capture metadata
- map sandbox paths → logical artifact paths
- expose artifacts to protocol layer

---

## 6.5 RunStateStore

Stores run-local memory.

Responsibilities:

- execution summaries
- step metadata
- current phase
- active subagent role

Persistence may be **in-memory for Milestone 1**.

---

# 7. Protocol Methods Implemented

Milestone 1 must implement these protocol endpoints:

runtime.health  
task.create  
task.get  
task.logs.stream  
task.artifacts.list  

---

# 8. Required Event Types

The runtime must emit at least these events.

task.created  
task.started  
plan.updated  
subagent.started  
tool.called  
artifact.created  
task.completed  
task.failed  

---

# 9. CLI Commands

agent health

agent run "task description"

agent status <task_id>

agent logs <task_id>

agent artifacts <task_id>

---

# 10. Reference Task for Milestone 1

Recommended task:

Inspect the workspace repository and generate a Markdown architecture summary.

Artifact output:

artifacts/repo_summary.md

---

# 11. Package Changes

apps/runtime

runtime_server.py  
task_runner.py  
event_bus.py  

services/deepagent-runtime

deepagent_harness.py  
tool_bindings.py  
prompt_builder.py  

services/sandbox-service

sandbox.py  
command_executor.py  
workspace_manager.py  

services/artifact-service

artifact_store.py  
artifact_registry.py  

services/memory-service

run_state_store.py  

---

# 12. CLI Improvements

Event streaming display and artifact listing table.

---

# 13. Testing Requirements

Unit Tests

sandbox path validation  
artifact registration  
task lifecycle transitions

Integration Tests

CLI → runtime protocol round trip  
task execution produces artifact  
event streaming works

Manual validation

start runtime  
run CLI task  
observe events  
inspect artifact

---

# 14. Milestone Acceptance Checklist

- CLI can submit tasks
- Runtime creates task + run ids
- Runtime invokes real AgentHarness
- Agent can read workspace files
- Agent can write artifact file
- Artifact registered in runtime
- CLI can list artifacts
- Events stream during execution
- task.get returns live state
- Architecture boundaries preserved

---

# 15. Next Milestone

Milestone 2 introduces:

durable project memory  
approval workflows  
resumable runs  
enhanced observability
