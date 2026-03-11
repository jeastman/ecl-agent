# MILESTONE-1 Implementation Blueprint
## Local Agent Harness — Single-Agent Runtime Vertical Slice

**Status:** Draft  
**Date:** 2026-03-10  
**Audience:** Runtime engineers, CLI engineers, AI coding agents  
**Purpose:** Concrete implementation blueprint for delivering Milestone 1

---

# 1. Blueprint Intent

This document translates `MILESTONE-1.md` into an implementation-ready blueprint.

It is designed to reduce ambiguity for developers and AI coding agents by defining:

- concrete package responsibilities
- initial interface shapes
- composition-root wiring
- runtime execution flow
- CLI command behavior
- test plan
- recommended implementation order

This is not the final code. It is the build map for the code.

---

# 2. Milestone 1 Outcome

At the end of Milestone 1, the repository should support one complete vertical slice:

1. a CLI command submits a task
2. the runtime accepts the task
3. the runtime executes the task through a real agent harness
4. the agent can read/write within a governed workspace
5. the runtime emits progress events
6. the runtime registers artifacts
7. the CLI can inspect task state, logs, and artifacts

The first supported use case should be:

> Inspect the repository workspace and generate a Markdown architecture summary artifact.

---

# 3. Recommended Build Order

Implement Milestone 1 in this order:

1. **Protocol-backed runtime skeleton**
2. **Run state store**
3. **Event bus**
4. **Artifact store**
5. **Sandbox implementation**
6. **AgentHarness interface + DeepAgent adapter**
7. **TaskRunner**
8. **Runtime server method wiring**
9. **CLI command wiring**
10. **Reference task verification path**
11. **Tests**
12. **Polish and acceptance validation**

This order ensures the team builds stable internal seams before attaching the actual agent.

---

# 4. Package Responsibility Map

## 4.1 `apps/runtime`
Owns the runtime entrypoint and protocol server.

Add:
- `runtime_server.py`
- `method_handlers.py`
- `task_runner.py`
- `event_bus.py`
- `bootstrap.py`

Responsibilities:
- stdio JSON-RPC loop
- request dispatch
- task lifecycle coordination
- event publishing to subscribed clients
- runtime service composition

## 4.2 `apps/cli`
Owns the user-facing CLI.

Add or update:
- command module for `health`
- command module for `run`
- command module for `status`
- command module for `logs`
- command module for `artifacts`
- runtime client transport wrapper

Responsibilities:
- argument parsing
- protocol requests
- event rendering
- snapshot/artifact formatting

## 4.3 `packages/protocol`
Owns typed contracts and schemas.

Add:
- request/response dataclasses or typed models
- event envelope models
- task/artifact/approval models
- protocol constants

Responsibilities:
- shared type system
- method names
- event names
- payload schema validation

## 4.4 `services/deepagent-runtime`
Owns the LangChain-specific adapter.

Add:
- `deepagent_harness.py`
- `prompt_builder.py`
- `tool_bindings.py`

Responsibilities:
- create/configure DeepAgent
- inject identity prompt context
- bind sandbox-backed tools
- translate streaming callbacks into runtime events

## 4.5 `services/sandbox-service`
Owns governed execution and filesystem access.

Add:
- `sandbox.py`
- `workspace_manager.py`
- `command_executor.py`
- `path_policy.py`

Responsibilities:
- workspace isolation
- scratch zone provisioning
- safe path normalization
- controlled command execution
- file operation helpers

## 4.6 `services/artifact-service`
Owns artifact registration.

Add:
- `artifact_store.py`
- `artifact_registry.py`

Responsibilities:
- artifact IDs
- metadata capture
- logical path mapping
- task/run artifact lookup

## 4.7 `services/memory-service`
Owns run-local state for Milestone 1.

Add:
- `run_state_store.py`

Responsibilities:
- current status
- active phase
- latest summary
- event history index
- per-run transient state

---

# 5. Concrete Runtime Interfaces

These interfaces should exist before the concrete implementations.

## 5.1 `AgentHarness`

```python
from dataclasses import dataclass
from typing import Callable, Protocol

EventCallback = Callable[[str, dict], None]

@dataclass
class AgentExecutionRequest:
    task_id: str
    run_id: str
    objective: str
    workspace_roots: list[str]
    identity_bundle_text: str
    allowed_capabilities: list[str]
    metadata: dict

@dataclass
class AgentExecutionResult:
    success: bool
    summary: str
    output_artifacts: list[str]
    error_message: str | None = None

class AgentHarness(Protocol):
    def execute(
        self,
        request: AgentExecutionRequest,
        on_event: EventCallback,
    ) -> AgentExecutionResult:
        ...
```

### Notes
- `on_event` emits runtime-friendly events, not framework-native events
- `output_artifacts` should contain sandbox-visible paths later resolved by the artifact store

## 5.2 `ExecutionSandbox`

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    cwd: str

class ExecutionSandbox(Protocol):
    def get_workspace_root(self) -> str:
        ...

    def get_scratch_root(self, task_id: str, run_id: str) -> str:
        ...

    def normalize_path(self, path: str) -> str:
        ...

    def read_text(self, path: str) -> str:
        ...

    def write_text(self, path: str, content: str) -> None:
        ...

    def exists(self, path: str) -> bool:
        ...

    def list_files(self, root: str) -> list[str]:
        ...

    def execute_command(
        self,
        command: list[str],
        cwd: str | None = None,
    ) -> CommandResult:
        ...
```

## 5.3 `ArtifactStore`

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class ArtifactRecord:
    artifact_id: str
    task_id: str
    run_id: str
    logical_path: str
    physical_path: str
    content_type: str
    created_at: str
    persistence_class: str
    source_role: str | None = None
    summary: str | None = None

class ArtifactStore(Protocol):
    def register_file(
        self,
        task_id: str,
        run_id: str,
        physical_path: str,
        logical_path: str,
        content_type: str,
        persistence_class: str = "run",
        source_role: str | None = None,
        summary: str | None = None,
    ) -> ArtifactRecord:
        ...

    def list_for_task(
        self,
        task_id: str,
        run_id: str | None = None,
    ) -> list[ArtifactRecord]:
        ...
```

## 5.4 `RunStateStore`

```python
from dataclasses import dataclass, field
from typing import Protocol

@dataclass
class RunState:
    task_id: str
    run_id: str
    status: str
    objective: str
    created_at: str
    updated_at: str
    current_phase: str | None = None
    latest_summary: str | None = None
    active_subagent: str | None = None
    artifact_count: int = 0
    event_ids: list[str] = field(default_factory=list)
    failure_message: str | None = None

class RunStateStore(Protocol):
    def create_run(self, state: RunState) -> None:
        ...

    def get_run(self, task_id: str, run_id: str | None = None) -> RunState | None:
        ...

    def update_run(self, state: RunState) -> None:
        ...
```

## 5.5 `EventBus`

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class RuntimeEvent:
    event_id: str
    event_type: str
    timestamp: str
    task_id: str
    run_id: str
    correlation_id: str
    source: dict
    payload: dict

class EventBus(Protocol):
    def publish(self, event: RuntimeEvent) -> None:
        ...

    def list_events(
        self,
        task_id: str,
        run_id: str | None = None,
        from_event_id: str | None = None,
    ) -> list[RuntimeEvent]:
        ...
```

---

# 6. Concrete Implementation Shapes

## 6.1 `InMemoryRunStateStore`

Use a dictionary keyed by `(task_id, run_id)`.

Behavior:
- create on `task.create`
- update status/phase/summary during execution
- support `task.get`
- enough for Milestone 1; no persistence across runtime restart

## 6.2 `InMemoryEventBus`

Use an append-only list per `(task_id, run_id)`.

Behavior:
- publish events in order
- allow replay for `task.logs.stream` with `include_history=true`
- enough for CLI polling/stream bootstrap behavior

## 6.3 `LocalArtifactStore`

Backed by in-memory metadata + filesystem-backed artifact files.

Behavior:
- assign `artifact_id`
- infer content type from extension when possible
- maintain `task_id/run_id -> [ArtifactRecord]`
- expose records for protocol

## 6.4 `LocalExecutionSandbox`

Initial implementation assumptions:
- single workspace root
- scratch root under runtime-managed temp or `.runtime/scratch/<task_id>/<run_id>/`
- memory root present but minimally used in Milestone 1

Behavior:
- reject paths escaping allowed roots
- normalize all paths before IO
- execute commands only within allowed cwd
- capture stdout/stderr fully for now

---

# 7. TaskRunner Blueprint

`TaskRunner` is the center of Milestone 1 runtime behavior.

## 7.1 Responsibilities
- create run state
- emit lifecycle events
- invoke `AgentHarness`
- register artifacts returned by the harness
- update final state
- handle failures consistently

## 7.2 Suggested shape

```python
class TaskRunner:
    def __init__(
        self,
        run_state_store: RunStateStore,
        event_bus: EventBus,
        artifact_store: ArtifactStore,
        agent_harness: AgentHarness,
    ) -> None:
        ...

    def start_run(
        self,
        correlation_id: str,
        objective: str,
        workspace_roots: list[str],
        identity_bundle_text: str,
        allowed_capabilities: list[str] | None = None,
        metadata: dict | None = None,
    ) -> tuple[str, str]:
        ...

    def get_task_snapshot(
        self,
        task_id: str,
        run_id: str | None = None,
    ) -> dict:
        ...

    def list_artifacts(
        self,
        task_id: str,
        run_id: str | None = None,
    ) -> list[dict]:
        ...
```

## 7.3 `start_run` flow

1. generate `task_id`
2. generate `run_id`
3. create initial `RunState(status="accepted")`
4. emit `task.created`
5. update to `planning` or `executing`
6. emit `task.started`
7. construct `AgentExecutionRequest`
8. invoke `agent_harness.execute(...)`
9. register artifacts in result
10. update state to `completed` or `failed`
11. emit final event
12. return `(task_id, run_id)`

## 7.4 Event callback bridge

The `TaskRunner` should pass a callback into the `AgentHarness`:

```python
def on_agent_event(event_type: str, payload: dict) -> None:
    # wrap into RuntimeEvent
    # append to event bus
    # update run state summary/phase when relevant
```

This keeps the harness unaware of the runtime event envelope mechanics.

---

# 8. DeepAgent Adapter Blueprint

## 8.1 File: `services/deepagent-runtime/deepagent_harness.py`

Create:

```python
class LangChainDeepAgentHarness(AgentHarness):
    def __init__(
        self,
        sandbox: ExecutionSandbox,
        prompt_builder: PromptBuilder,
    ) -> None:
        ...

    def execute(
        self,
        request: AgentExecutionRequest,
        on_event: EventCallback,
    ) -> AgentExecutionResult:
        ...
```

## 8.2 Milestone 1 design constraint

The adapter should support a **minimal but real** DeepAgent configuration:
- one primary agent role
- no real sub-agent orchestration yet
- toolset limited to sandbox-backed operations
- prompt includes identity context and explicit task objective

## 8.3 Tool binding plan

In `tool_bindings.py`, create sandbox-backed tools such as:
- `read_file`
- `write_file`
- `list_files`
- `execute_command`

Each tool should:
1. call `on_event("tool.called", ...)`
2. delegate to the sandbox
3. return concise structured results

## 8.4 Prompt builder

In `prompt_builder.py`:

```python
class PromptBuilder:
    def build_system_prompt(
        self,
        identity_bundle_text: str,
        workspace_roots: list[str],
    ) -> str:
        ...
```

Prompt content should include:
- identity doctrine
- workspace boundaries
- artifact expectations
- instruction to create a markdown summary artifact for the reference task

## 8.5 Initial event mapping

The adapter should emit at least:
- `plan.updated`
- `subagent.started` with role `"primary"` or `"coder"`
- `tool.called`

If the framework cannot produce plan callbacks directly in a clean way for the first pass, synthesize a simple `plan.updated` event from the adapter before execution begins.

---

# 9. Sandbox Blueprint

## 9.1 File: `services/sandbox-service/path_policy.py`

Implement rules:
- only allow reads/writes under configured workspace root and runtime scratch root
- reject path traversal escaping those roots
- normalize symlinks conservatively if used
- raise a typed exception on violation

## 9.2 File: `services/sandbox-service/workspace_manager.py`

Responsibilities:
- provide workspace root
- create scratch directory
- create memory directory placeholder
- expose helper functions for runtime

## 9.3 File: `services/sandbox-service/command_executor.py`

Implementation notes:
- use `subprocess.run`
- accept `command: list[str]`
- pass explicit cwd
- capture stdout/stderr
- use timeout support even if fixed for Milestone 1
- return `CommandResult`

## 9.4 File: `services/sandbox-service/sandbox.py`

Compose the path policy, workspace manager, and command executor.

The sandbox is the only place where filesystem and command side effects occur.

---

# 10. Artifact Registration Blueprint

## 10.1 Artifact strategy

Artifacts should be registered by the runtime, not the harness directly.

The harness returns file paths. The `TaskRunner` converts those into artifact records.

## 10.2 Logical path mapping

Recommended rule:
- if the file lives under workspace root, logical path is relative to workspace root
- if the file lives under scratch root, logical path is relative to scratch root but prefixed with `scratch/`

## 10.3 Initial content type mapping

Map common extensions:
- `.md` → `text/markdown`
- `.txt` → `text/plain`
- `.json` → `application/json`
- fallback → `application/octet-stream`

---

# 11. Runtime Server Blueprint

## 11.1 File: `apps/runtime/bootstrap.py`

Build all runtime services here.

```python
def build_runtime() -> RuntimeServer:
    ...
```

Compose:
- sandbox
- artifact store
- run state store
- event bus
- prompt builder
- agent harness
- task runner
- method handlers

## 11.2 File: `apps/runtime/runtime_server.py`

Responsibilities:
- read JSON-RPC messages from stdio
- dispatch to handlers
- write responses
- emit runtime event envelopes

## 11.3 File: `apps/runtime/method_handlers.py`

Implement handlers for:
- `runtime.health`
- `task.create`
- `task.get`
- `task.logs.stream`
- `task.artifacts.list`

### Suggested handler signatures

```python
class MethodHandlers:
    def runtime_health(self, params: dict) -> dict:
        ...

    def task_create(self, params: dict) -> dict:
        ...

    def task_get(self, params: dict) -> dict:
        ...

    def task_logs_stream(self, params: dict) -> dict:
        ...

    def task_artifacts_list(self, params: dict) -> dict:
        ...
```

## 11.4 Streaming behavior for Milestone 1

A practical first implementation:
- `task.logs.stream` returns stream open confirmation
- runtime emits all current history immediately if requested
- runtime then emits newly published events to stdout as `type: "runtime.event"`

This is sufficient for the CLI to behave like a live stream.

---

# 12. CLI Blueprint

## 12.1 Command surface

Implement:

```bash
agent health
agent run "Generate repository architecture summary"
agent status <task_id>
agent logs <task_id>
agent artifacts <task_id>
```

## 12.2 Suggested internal modules

- `client.py`
- `commands/health.py`
- `commands/run.py`
- `commands/status.py`
- `commands/logs.py`
- `commands/artifacts.py`
- `renderers/events.py`
- `renderers/table.py`

## 12.3 Rendering guidance

### `agent run`
- submit the task
- print `task_id` and `run_id`
- optionally suggest `agent logs <task_id>`

### `agent status`
Render:
- task id
- run id
- status
- objective
- latest summary
- active subagent
- artifact count

### `agent logs`
Render a readable event timeline, for example:

```text
[task.started] execution started
[plan.updated] planner created a 3-step plan
[subagent.started] primary
[tool.called] list_files
[artifact.created] artifacts/repo_summary.md
[task.completed] success
```

### `agent artifacts`
Render a simple table:
- artifact id
- logical path
- content type
- persistence class

---

# 13. Reference Task Behavior

## 13.1 Reference task objective

Use this during development and testing:

> Generate a Markdown architecture summary for the repository.

## 13.2 Expected agent behavior

The agent should:
1. inspect the repository tree
2. read key files like `README.md`
3. produce a concise architecture summary
4. write it to a markdown file
5. return the artifact path to the runtime

## 13.3 Expected artifact location

Preferred:
```text
<workspace_root>/artifacts/repo_summary.md
```

Fallback:
```text
<scratch_root>/repo_summary.md
```

---

# 14. Testing Blueprint

## 14.1 Unit tests

### Sandbox
- rejects path traversal
- allows in-root reads/writes
- executes commands in allowed cwd only

### ArtifactStore
- registers file metadata correctly
- lists artifacts by task/run
- assigns stable IDs

### RunStateStore
- creates run
- updates run
- fetches latest run

### TaskRunner
- emits correct lifecycle events
- updates final state on success
- updates final state on failure

## 14.2 Integration tests

### Runtime protocol
- `runtime.health` returns ok
- `task.create` returns ids
- `task.get` returns live state
- `task.artifacts.list` returns created artifact

### End-to-end reference task
- start runtime
- submit reference task
- confirm artifact created
- confirm `task.completed` emitted

### CLI round trip
- CLI can call runtime
- CLI can render snapshot
- CLI can render artifacts

## 14.3 Test doubles

Create lightweight fakes for:
- `AgentHarness`
- `ExecutionSandbox`
- `ArtifactStore`
- `EventBus`

Use these to validate `TaskRunner` independently from DeepAgent.

---

# 15. Acceptance Walkthrough

A Milestone 1 manual validation should look like this:

## Step 1
Start the runtime.

## Step 2
Run:

```bash
agent run "Generate repository architecture summary"
```

## Step 3
Observe returned task/run IDs.

## Step 4
Run:

```bash
agent logs <task_id>
```

Verify:
- `task.created`
- `task.started`
- `plan.updated`
- `tool.called`
- `artifact.created`
- `task.completed`

## Step 5
Run:

```bash
agent artifacts <task_id>
```

Verify the markdown artifact is listed.

## Step 6
Run:

```bash
agent status <task_id>
```

Verify:
- status is `completed`
- artifact count is correct
- latest summary is present

---

# 16. Anti-Patterns to Avoid

Do not:
- place task lifecycle logic in the CLI
- let LangChain classes leak into shared packages
- let the agent read/write arbitrary host paths
- have the harness register artifacts directly into protocol responses
- make protocol payloads ad hoc or untyped
- overbuild durable memory in Milestone 1

---

# 17. Suggested File Skeleton

```text
apps/
  runtime/
    bootstrap.py
    runtime_server.py
    method_handlers.py
    task_runner.py
    event_bus.py

  cli/
    client.py
    commands/
      health.py
      run.py
      status.py
      logs.py
      artifacts.py
    renderers/
      events.py
      table.py

services/
  deepagent-runtime/
    deepagent_harness.py
    prompt_builder.py
    tool_bindings.py

  sandbox-service/
    sandbox.py
    workspace_manager.py
    command_executor.py
    path_policy.py

  artifact-service/
    artifact_store.py
    artifact_registry.py

  memory-service/
    run_state_store.py
```

---

# 18. Minimal Pseudocode Flow

```python
# task.create
task_id, run_id = task_runner.start_run(
    correlation_id=params["correlation_id"],
    objective=params["task"]["objective"],
    workspace_roots=params["task"]["workspace_roots"],
    identity_bundle_text=identity_bundle_loader.load(...),
    allowed_capabilities=params["task"].get("allowed_capabilities", []),
    metadata=params["task"].get("metadata", {}),
)
return {
    "task_id": task_id,
    "run_id": run_id,
    "status": "accepted",
}
```

```python
# inside TaskRunner.start_run
create_run_state(...)
publish("task.created", ...)
publish("task.started", ...)

result = agent_harness.execute(request, on_event=publish_bridge)

for artifact_path in result.output_artifacts:
    artifact = artifact_store.register_file(..., physical_path=artifact_path, ...)
    publish("artifact.created", {"artifact": artifact_to_dict(artifact)})

if result.success:
    update_run_state(status="completed", latest_summary=result.summary)
    publish("task.completed", ...)
else:
    update_run_state(status="failed", failure_message=result.error_message)
    publish("task.failed", ...)
```

---

# 19. Exit Criteria

This blueprint is fulfilled when the codebase contains a working Milestone 1 implementation that:

- executes a real task through the runtime
- uses a real DeepAgent-backed harness adapter
- works through the sandbox abstraction
- emits protocol-compliant events
- registers artifacts
- supports CLI inspection commands
- preserves the architecture boundaries established in Milestone 0

---

# 20. Next Step After This Blueprint

Once this blueprint is accepted, the next useful artifact would be a **Codex/Cursor implementation prompt pack** that breaks Milestone 1 into sequenced coding prompts for an AI coding agent.
