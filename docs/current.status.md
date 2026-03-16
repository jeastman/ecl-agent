# Current Status: Implementation vs. Master Spec

This document compares the repository implementation to [local-agent-harness-master-spec-v1.md](/Users/jeastman/Projects/e/ecl-agent/docs/specs/local-agent-harness-master-spec-v1.md) based on direct verification of the current codebase on March 15, 2026.

It is intentionally implementation-first. Statements below are grounded in source files, repository structure, runtime configuration, and the current automated checks.

## Verification Basis

The comparison below was verified against:

- runtime code under `apps/runtime/local_agent_runtime`
- CLI code under `apps/cli/local_agent_cli`
- TUI code under `apps/tui/local_agent_tui`
- shared packages under `packages/*`
- service implementations under `services/*`
- agent assets under `agents/*`
- runtime example configuration at [runtime.example.toml](/Users/jeastman/Projects/e/ecl-agent/docs/architecture/runtime.example.toml)
- automated tests under `tests/*`

Verification commands executed in this workspace:

```bash
uv run pytest
uv run ruff check .
```

Observed results:

```text
233 passed in 24.18s
F401 [*] `.widgets.status_bar.StatusBar` imported but unused
  --> apps/tui/local_agent_tui/app.py:48:33
```

Current interpretation:

- the test suite passes
- the repository is not fully lint-clean at the moment because of one unused import in the TUI app

## Executive Summary

The repository materially exceeds the earlier Milestone 2 framing that still appears in some older documentation. The codebase now implements:

- the Milestone 0 repository and contract foundation
- the Milestone 1 single-runtime execution slice
- the Milestone 2 durable runtime-governance baseline
- the Milestone 3 subagent, routing, and governed skill-installation baseline
- a local Textual TUI operator client on top of the same runtime protocol

The practical result is:

- the master spec section 28 initial architecture baseline is satisfied
- Milestones 0 through 3 are substantially implemented
- Milestone 4 is still incomplete, but not empty in the broad "operator experience" sense because the TUI already provides local task browsing, artifact preview, event review, approvals, diagnostics, memory inspection, and config inspection

The main remaining gaps are:

- no web client
- no `task.cancel`
- richer memory retrieval and governance semantics are still narrower than the long-term spec intent

## Status Legend

- `Implemented`: present in code and wired into runtime or client behavior
- `Partial`: some structures exist, but behavior is incomplete or narrower than the broader spec intent
- `Not Implemented`: the spec calls for it, but the current repository does not implement it

## 1. Overall Standing Against the Master Spec

The master spec is best read in two layers:

1. the initial architecture baseline in section 28
2. the milestone roadmap in section 26

Against section 28, the repository is in strong shape. Against section 26, the repository has completed the first four roadmap stages through Milestone 3. Milestone 4 remains incomplete because the web-facing client/platform work is not present.

That means the honest current position is:

- the foundational runtime/client architecture is in place
- the durable runtime-governance features expected after Milestone 1 are in place
- the subagent system expected in Milestone 3 is in place with real execution paths
- the repository now has two clients, but still lacks the web client implied by later roadmap stages

## 2. Acceptance Criteria Check (Master Spec Section 28)

Master spec section 28 says the initial architecture baseline is satisfied when ten conditions hold.

Current status:

- `Implemented`: 10 of 10
- `Partial`: 0 of 10
- `Not Implemented`: 0 of 10

Conclusion:

- the repository satisfies the master spec's initial architecture baseline

| Acceptance criterion | Status | Notes |
| --- | --- | --- |
| Distinct runtime and client applications exist | Implemented | `apps/runtime`, `apps/cli`, and `apps/tui` are separate and have separate responsibilities |
| Runtime exposes a transport-neutral protocol contract implemented over stdio | Implemented | JSON-RPC 2.0 over stdio is implemented in the runtime server and used by both clients |
| Task execution responsibility resides in the runtime | Implemented | `TaskRunner`, runtime handlers, and the runtime server own lifecycle and execution |
| LangChain DeepAgent is isolated behind project-owned ports/adapters | Implemented | DeepAgent usage is contained in `services/deepagent_runtime` behind project-owned boundaries |
| Memory taxonomy exists as explicit concepts in the codebase | Implemented | `run_state`, `project`, `identity`, and `scratch` exist as explicit runtime memory scopes |
| Sandbox/filesystem access is mediated by a dedicated abstraction | Implemented | sandbox, path policy, workspace manager, and command executor mediate access |
| Model routing supports separate profiles for primary and subagents | Implemented | runtime-owned model resolution exists for the primary harness and subagent roles |
| `IDENTITY.md` ingestion exists as a runtime concern | Implemented | identity loading, hashing, versioning, prompt construction, and memory seeding happen in runtime bootstrap |
| Event streaming exists for task lifecycle visibility | Implemented | runtime events are emitted, stored durably, replayed, and consumed by both clients |
| Codebase structure clearly supports future clients | Implemented | shared protocol/config/task packages plus thin clients preserve that separation |

## 3. Milestone Status

### 3.1 Milestone 0

**Observed status:** `Implemented`

Verified deliverables:

- monorepo skeleton
- shared protocol package
- shared config package
- shared task model package
- runtime composition shell
- identity ingestion shell
- thin client shell
- ADR pack under `docs/adr/`

### 3.2 Milestone 1

**Observed status:** `Implemented`

Verified deliverables:

- one primary DeepAgent behind the project-owned adapter boundary
- local governed sandbox implementation
- runtime-owned task execution
- event streaming
- artifact capture
- run-local task state

### 3.3 Milestone 2

**Observed status:** `Implemented`

Verified deliverables:

- durable project memory store
- checkpoint persistence and resumption support
- runtime-owned approval contract and policy engine
- richer observability than the Milestone 1 slice
- memory inspection support

Concrete implemented evidence includes:

- durable runtime services composed in [durable_services.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/durable_services.py)
- checkpoint store and thread registry under `services/checkpoint_service`
- SQLite-backed memory, approval, event, diagnostics, and metrics stores
- runtime recovery in [recovery_service.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/recovery_service.py)
- resume flow in [resume_service.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/resume_service.py)
- protocol support for `task.resume`, `task.reply`, `task.approve`, `task.approvals.list`, `task.diagnostics.list`, `memory.inspect`, and `config.get`

### 3.4 Milestone 3

**Observed status:** `Implemented`

Verified deliverables:

- subagent registry
- role-based tool scopes
- runtime model routing
- planner/researcher/coder/verifier role assets
- delegated subagent execution through the primary harness
- governed skill installation into managed skill roots

Concrete implemented evidence includes:

- filesystem-backed registry in [filesystem_subagent_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_registry/local_agent_subagent_registry/filesystem_subagent_registry.py)
- role tool-scope resolution in [tool_scope.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/tool_scope.py)
- runtime-owned model routing in [model_routing.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/model_routing.py)
- adapter-side subagent compilation and execution in [deepagent_harness.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/deepagent_harness.py)
- runtime-owned skill installation in [skill_installer.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_installer.py)
- role assets under `agents/subagents/planner`, `researcher`, `coder`, `verifier`, and `librarian`
- runtime-visible `subagent.started` and `subagent.completed` events

Important nuance:

- the repository implements runtime-owned role definitions, routing, scopes, and a real delegated execution path
- it does not implement a bespoke hard-coded orchestration graph outside DeepAgent

That still satisfies the architectural intent of Milestone 3 because the required project-owned role system and live execution path are present.

### 3.5 Milestone 4

**Observed status:** `Partial`

Implemented today:

- a local Textual TUI client
- task browsing via `task.list`
- artifact browsing and preview via `task.artifacts.list` and `task.artifact.get`
- event review and live stream consumption
- operator screens for approvals, diagnostics, memory, and config

Not present today:

- web client
- remote/live artifact browser outside the local TUI
- broader multi-client platform packaging or SDK layers suggested by later roadmap language

This is why Milestone 4 is best described as partial rather than absent.

## 4. Architecture Areas

### 4.1 Runtime and Client Separation

**Observed implementation:** `Implemented`

The runtime owns execution, lifecycle, artifacts, approvals, checkpoints, memory inspection, and event emission. The CLI and TUI remain protocol clients and renderers.

Primary evidence:

- [task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py)
- [method_handlers.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/method_handlers.py)
- [runtime_server.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/runtime_server.py)
- [cli.py](/Users/jeastman/Projects/e/ecl-agent/apps/cli/local_agent_cli/cli.py)
- [protocol_client.py](/Users/jeastman/Projects/e/ecl-agent/apps/tui/local_agent_tui/protocol/protocol_client.py)
- [app.py](/Users/jeastman/Projects/e/ecl-agent/apps/tui/local_agent_tui/app.py)

### 4.2 DeepAgent Containment

**Observed implementation:** `Implemented`

Direct DeepAgent and LangChain construction remains contained to the adapter layer. The rest of the runtime deals in project-owned request/result models, runtime events, and governed tool bindings.

Primary evidence:

- [deepagent_harness.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/deepagent_harness.py)
- [tool_bindings.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/tool_bindings.py)

### 4.3 Memory Model

**Observed implementation:** `Implemented` for the section 28 baseline, `Partial` for the broader spec ambition

What is implemented:

- explicit memory scopes: `run_state`, `project`, `identity`, `scratch`
- durable SQLite-backed memory storage
- memory promotion from agent-writable scopes into project memory
- identity seeding into memory
- runtime inspection via `memory.inspect`

What remains incomplete relative to the broader spec language:

- richer retrieval precedence behavior is not yet implemented as a first-class runtime policy
- memory governance is still narrower than the long-term spec intent

Primary evidence:

- [memory_promotion.py](/Users/jeastman/Projects/e/ecl-agent/services/memory_service/local_agent_memory_service/memory_promotion.py)
- [memory_store.py](/Users/jeastman/Projects/e/ecl-agent/services/memory_service/local_agent_memory_service/memory_store.py)
- [memory_seed.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/memory_seed.py)
- [method_handlers.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/method_handlers.py)

### 4.4 Sandbox and Filesystem Policy

**Observed implementation:** `Implemented`

The repo satisfies the spec's sandbox boundary requirements for the local-first runtime:

- governed workspace, scratch, and memory zones
- path normalization and traversal rejection
- command execution only through the sandbox abstraction
- runtime-owned policy checks on governed operations

Primary evidence:

- [sandbox.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/sandbox.py)
- [workspace_manager.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/workspace_manager.py)
- [path_policy.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/path_policy.py)
- [command_executor.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/command_executor.py)

### 4.5 Identity and Policy

**Observed implementation:** `Implemented`

Identity is a real runtime concern, not a client concern. Policy and approvals are runtime-owned and durable.

Implemented:

- `IDENTITY.md` loading, hashing, and versioning
- prompt construction using identity content
- durable approval storage
- runtime-owned policy decisions: allow, require approval, deny
- boundary-scoped approval grants
- approval-oriented pause/resume flow

Primary evidence:

- [loader.py](/Users/jeastman/Projects/e/ecl-agent/packages/identity/local_agent_identity/loader.py)
- [policy_engine.py](/Users/jeastman/Projects/e/ecl-agent/services/policy_service/local_agent_policy_service/policy_engine.py)
- [task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py)

### 4.6 Subagents, Skills, and Model Routing

**Observed implementation:** `Implemented`

Implemented:

- filesystem-backed subagent registry
- role manifests and asset bundles
- role-scoped tools
- role-local skill discovery
- runtime-owned primary and subagent model resolution
- adapter-side compilation of runtime-owned roles into live DeepAgent-native subagents
- runtime-governed skill installation into managed primary-agent and subagent skill roots

Still narrower than the broadest possible reading of the spec:

- primary-agent skills are still lighter than the subagent role setup
- delegated-execution telemetry is useful, but not yet especially deep

Primary evidence:

- [bootstrap.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/bootstrap.py)
- [filesystem_subagent_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_registry/local_agent_subagent_registry/filesystem_subagent_registry.py)
- [skill_catalog.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_catalog.py)
- [skill_installer.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_installer.py)
- [skill_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_registry.py)
- [model_routing.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/model_routing.py)
- [deepagent_harness.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/deepagent_harness.py)

### 4.7 Protocol Surface and Clients

**Observed implementation:** `Implemented`

The runtime method surface is broader than the older repo-level README claimed.

Implemented runtime methods:

- `runtime.health`
- `task.create`
- `task.list`
- `task.get`
- `task.approve`
- `task.approvals.list`
- `task.diagnostics.list`
- `task.reply`
- `task.resume`
- `task.logs.stream`
- `task.artifacts.list`
- `task.artifact.get`
- `memory.inspect`
- `skill.install`
- `config.get`

Client coverage:

- the CLI exposes the operator command path for most runtime methods, including `reply` and `skill-install`
- the TUI consumes `task.list`, `task.artifact.get`, live event streams, approvals, diagnostics, memory inspection, and config inspection

Primary evidence:

- [models.py](/Users/jeastman/Projects/e/ecl-agent/packages/protocol/local_agent_protocol/models.py)
- [cli.py](/Users/jeastman/Projects/e/ecl-agent/apps/cli/local_agent_cli/cli.py)
- [protocol_client.py](/Users/jeastman/Projects/e/ecl-agent/apps/tui/local_agent_tui/protocol/protocol_client.py)
- [runtime_server.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/runtime_server.py)

### 4.8 Observability and Artifacting

**Observed implementation:** `Implemented` for the runtime baseline, `Partial` for broader future operator UX

Implemented:

- append-only per-run event history
- persisted event store
- persisted diagnostics store
- persisted run metrics store
- runtime-owned artifact registration
- artifact metadata listing plus preview retrieval
- CLI log/event rendering
- TUI timeline, artifact browser, markdown preview, approval queue, diagnostics, memory, and config views

The skill-installation flow specifically adds:

- `skill.install.requested`, `skill.install.validated`, `skill.install.approval_requested`, `skill.install.completed`, and `skill.install.failed` runtime events
- validation report, install summary, file manifest, and conflict report artifacts for skill installation runs

Not yet implemented:

- web/operator visualization layer
- richer external tracing integrations

Primary evidence:

- [event_store.py](/Users/jeastman/Projects/e/ecl-agent/services/observability_service/local_agent_observability_service/event_store.py)
- [diagnostic_store.py](/Users/jeastman/Projects/e/ecl-agent/services/observability_service/local_agent_observability_service/diagnostic_store.py)
- [run_metrics_store.py](/Users/jeastman/Projects/e/ecl-agent/services/observability_service/local_agent_observability_service/run_metrics_store.py)
- [store.py](/Users/jeastman/Projects/e/ecl-agent/services/artifact_service/local_agent_artifact_service/store.py)
- [app.py](/Users/jeastman/Projects/e/ecl-agent/apps/tui/local_agent_tui/app.py)

## 5. Verified Gaps Relative to the Broader Spec and Follow-on Direction

These are the main remaining gaps after the current Milestone 3 baseline:

1. `task.cancel` is still not implemented.
2. `memory.updated` is still not part of the current event vocabulary.
3. Memory retrieval precedence and richer governance semantics remain incomplete.
4. There is no web client.
5. The codebase structurally supports future clients, but broader SDK/platform packaging suggested by later roadmap language does not exist yet.
6. The repository currently has a small lint regression in the TUI app.

None of those gaps invalidate the section 28 baseline. They do matter for the next stage of platform maturity.

## 6. Bottom Line

The honest status is:

- the repository satisfies the master spec's initial architecture baseline
- Milestones 0 through 3 are substantially implemented in code
- the repository now has both a CLI and a local TUI client
- the repo is stronger than the older Milestone 2-oriented documentation claimed
- the main unfinished work sits in web-client/platform territory plus some broader memory and lifecycle semantics

What is real today is a local-first agent runtime with:

- thin clients over a formal stdio protocol
- runtime-owned execution lifecycle
- a contained DeepAgent adapter
- governed filesystem and command execution
- durable checkpoints, approvals, diagnostics, metrics, and event history
- explicit memory scopes with durable project memory
- restart recovery, resume, and user-reply support
- project-owned subagent roles with model routing and delegated execution
- governed skill installation into managed skill roots

What is not yet real today is the web client, cancellation, and the broader memory-governance maturity described in the long-range spec.
