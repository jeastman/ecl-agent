# Current Status: Implementation vs. Master Spec

This document compares the repository implementation to [local-agent-harness-master-spec-v1.md](/Users/jeastman/Projects/e/ecl-agent/docs/specs/local-agent-harness-master-spec-v1.md) based on direct verification of the current codebase on March 20, 2026.

It is intentionally implementation-first. Statements below are grounded in the current source tree, protocol models, runtime handlers, clients, and automated checks.

## Verification Basis

Verified against:

- runtime code under `apps/runtime/local_agent_runtime`
- CLI code under `apps/cli/local_agent_cli`
- TUI code under `apps/tui/local_agent_tui`
- shared packages under `packages/*`
- service implementations under `services/*`
- agent and subagent assets under `agents/*`
- runtime example configuration at [runtime.example.toml](/Users/jeastman/Projects/e/ecl-agent/docs/architecture/runtime.example.toml)
- automated tests under `tests/*`

Verification commands executed in this workspace:

```bash
uv run pytest
uv run ruff check .
```

Observed results:

```text
pytest: 461 passed, 3 failed in 37.75s
ruff: 60 errors
```

Current verification notes:

- the repository is not currently test-green
- the failing tests are:
  - missing persisted `subagent.started` events in two runtime integration tests
  - a TUI footer-hint expectation mismatch (`Esc` now renders as `Back` instead of `Dashboard`)
- the repository is also not lint-clean; the current Ruff output reports 60 issues rather than a single unused import

## Executive Summary

The repository is beyond the older Milestone 2 framing. The current implementation includes:

- the Milestone 0 repository and contract foundation
- the Milestone 1 single-runtime execution slice
- the Milestone 2 durable runtime-governance baseline
- the Milestone 3 subagent, routing, conversation-compaction, and governed skill-installation baseline
- a local Textual TUI operator client over the same runtime protocol

The practical status today is:

- the master spec section 28 architecture baseline is implemented in code
- Milestones 0 through 3 are substantially implemented
- Milestone 4 remains partial because there is still no web client
- the runtime surface is broader than older docs claimed: `task.reply`, `task.resume`, `task.compact`, `memory.inspect`, `skill.install`, and `config.get` are all implemented
- some live regressions remain, so the repo should not be described as fully green

The main remaining gaps are:

- no `task.cancel`
- no web client
- memory retrieval/governance is still narrower than the long-range spec intent
- current regressions around subagent start-event persistence and TUI footer-hint expectations

## Status Legend

- `Implemented`: present in code and wired into runtime or client behavior
- `Partial`: some structures exist, but behavior is incomplete, regressed, or narrower than the broader spec intent
- `Not Implemented`: the spec calls for it, but the current repository does not implement it

## 1. Overall Standing Against the Master Spec

The master spec is best read in two layers:

1. the initial architecture baseline in section 28
2. the milestone roadmap in section 26

Against section 28, the repository still satisfies the architectural baseline. Against section 26, the implementation has moved through Milestone 3 and part of Milestone 4, but it is not yet at the later web-client/platform stage.

That means the current position is:

- the foundational runtime/client split is in place
- the durable runtime-governance features expected after Milestone 1 are in place
- the subagent system expected in Milestone 3 is in place
- conversation compaction is implemented in config, runtime handlers, task state, and persistence
- the repository has two clients today: CLI and local TUI
- the later web-facing client work is still absent

## 2. Acceptance Criteria Check (Master Spec Section 28)

Master spec section 28 says the initial architecture baseline is satisfied when ten conditions hold.

Current status:

- `Implemented`: 10 of 10
- `Partial`: 0 of 10
- `Not Implemented`: 0 of 10

Conclusion:

- the repository still satisfies the master spec's initial architecture baseline
- that architectural conclusion is separate from the fact that the repo currently has failing tests and lint issues

| Acceptance criterion | Status | Notes |
| --- | --- | --- |
| Distinct runtime and client applications exist | Implemented | `apps/runtime`, `apps/cli`, and `apps/tui` are separate |
| Runtime exposes a transport-neutral protocol contract implemented over stdio | Implemented | JSON-RPC 2.0 over stdio is implemented and used by both clients |
| Task execution responsibility resides in the runtime | Implemented | `TaskRunner`, runtime handlers, and the runtime server own lifecycle and execution |
| LangChain DeepAgent is isolated behind project-owned ports/adapters | Implemented | DeepAgent usage remains contained in `services/deepagent_runtime` |
| Memory taxonomy exists as explicit concepts in the codebase | Implemented | `run_state`, `project`, `identity`, and `scratch` exist as explicit scopes |
| Sandbox/filesystem access is mediated by a dedicated abstraction | Implemented | sandbox, path policy, workspace manager, and command executor mediate access |
| Model routing supports separate profiles for primary and subagents | Implemented | runtime-owned model resolution exists for both |
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
- redacted config inspection support

Concrete evidence includes:

- durable runtime services composed in [durable_services.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/durable_services.py)
- checkpoint store and thread registry under `services/checkpoint_service`
- SQLite-backed memory, approval, event, diagnostics, metrics, and conversation-compaction stores
- runtime recovery in [recovery_service.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/recovery_service.py)
- resume flow in [resume_service.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/resume_service.py)
- protocol support for `task.resume`, `task.reply`, `task.approve`, `task.approvals.list`, `task.diagnostics.list`, `memory.inspect`, and `config.get`

### 3.4 Milestone 3

**Observed status:** `Implemented`

Verified deliverables:

- subagent registry
- role-based tool scopes
- runtime model routing
- planner/researcher/coder/verifier/librarian role assets
- delegated subagent execution through the primary harness
- governed skill installation into managed skill roots
- conversation compaction support across runtime, protocol, state, and persistence

Concrete evidence includes:

- filesystem-backed registry in [filesystem_subagent_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_registry/local_agent_subagent_registry/filesystem_subagent_registry.py)
- role tool-scope resolution in [tool_scope.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/tool_scope.py)
- runtime-owned model routing in [model_routing.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/model_routing.py)
- delegated subagent event middleware in [subagent_compiler.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/subagent_compiler.py)
- adapter-side subagent compilation and execution in [deepagent_harness.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/deepagent_harness.py)
- runtime-owned skill installation in [skill_installer.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_installer.py)
- conversation compaction integration in [task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py) and [conversation_compaction_service.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/conversation_compaction_service.py)

Important nuance:

- the code defines and tests both `subagent.started` and `subagent.completed`
- the current integration suite shows a regression where `subagent.started` is not present in persisted runtime history for some paths
- that is best described as an implementation regression inside an otherwise implemented Milestone 3 slice

### 3.5 Milestone 4

**Observed status:** `Partial`

Implemented today:

- a local Textual TUI client
- task browsing via `task.list`
- artifact browsing and preview via `task.artifacts.list` and `task.artifact.get`
- event review and live stream consumption
- operator screens for approvals, diagnostics, memory, and config
- task-detail command input for replies and action dispatch

Not present today:

- web client
- broader remote/multi-client platform packaging suggested by later roadmap language

## 4. Architecture Areas

### 4.1 Runtime and Client Separation

**Observed implementation:** `Implemented`

The runtime owns execution, lifecycle, artifacts, approvals, checkpoints, memory inspection, config inspection, and event emission. The CLI and TUI remain protocol clients and renderers.

Primary evidence:

- [task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py)
- [method_handlers.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/method_handlers.py)
- [runtime_server.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/runtime_server.py)
- [cli.py](/Users/jeastman/Projects/e/ecl-agent/apps/cli/local_agent_cli/cli.py)
- [protocol_client.py](/Users/jeastman/Projects/e/ecl-agent/apps/tui/local_agent_tui/protocol/protocol_client.py)

### 4.2 DeepAgent Containment

**Observed implementation:** `Implemented`

Direct DeepAgent and LangChain construction remains contained to the adapter layer. The rest of the runtime deals in project-owned request/result models, runtime events, task state, and governed tool bindings.

Primary evidence:

- [deepagent_harness.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/deepagent_harness.py)
- [tool_bindings.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/tool_bindings.py)

### 4.3 Memory Model

**Observed implementation:** `Implemented` for the section 28 baseline, `Partial` for the broader spec ambition

What is implemented:

- explicit memory scopes: `run_state`, `project`, `identity`, `scratch`
- durable SQLite-backed memory storage
- memory promotion into project memory
- identity seeding into memory
- runtime inspection via `memory.inspect`
- `memory.updated` event emission on memory writes

What remains incomplete relative to the broader spec language:

- richer retrieval precedence behavior is not yet implemented as a first-class runtime policy
- memory governance is still narrower than the long-term spec intent

Primary evidence:

- [memory_promotion.py](/Users/jeastman/Projects/e/ecl-agent/services/memory_service/local_agent_memory_service/memory_promotion.py)
- [memory_store.py](/Users/jeastman/Projects/e/ecl-agent/services/memory_service/local_agent_memory_service/memory_store.py)
- [memory_seed.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/memory_seed.py)
- [tool_bindings.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/tool_bindings.py)

### 4.4 Sandbox and Filesystem Policy

**Observed implementation:** `Implemented`

The repo satisfies the sandbox boundary requirements for the local-first runtime:

- governed workspace, scratch, and memory zones
- path normalization and traversal rejection
- command execution through the sandbox abstraction
- runtime-owned policy checks on governed operations

Primary evidence:

- [sandbox.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/sandbox.py)
- [workspace_manager.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/workspace_manager.py)
- [path_policy.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/path_policy.py)
- [command_executor.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/command_executor.py)

### 4.5 Identity and Policy

**Observed implementation:** `Implemented`

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

### 4.6 Subagents, Skills, Model Routing, and Compaction

**Observed implementation:** `Implemented`

Implemented:

- filesystem-backed subagent registry
- role manifests and asset bundles
- role-scoped tools
- role-local skill discovery
- runtime-owned primary and subagent model resolution
- adapter-side compilation of runtime-owned roles into live DeepAgent-native subagents
- governed skill installation into managed primary-agent and subagent skill roots
- explicit `task.compact` protocol and runtime support
- persisted conversation compaction projections and task snapshot links

Still narrower than the broadest possible reading of the spec:

- memory/governance semantics are still lighter than the long-range target
- current subagent start-event persistence has a regression in integration coverage

Primary evidence:

- [bootstrap.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/bootstrap.py)
- [filesystem_subagent_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_registry/local_agent_subagent_registry/filesystem_subagent_registry.py)
- [skill_catalog.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_catalog.py)
- [skill_installer.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_installer.py)
- [skill_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_registry.py)
- [model_routing.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/model_routing.py)
- [task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py)

### 4.7 Protocol Surface and Clients

**Observed implementation:** `Implemented`

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
- `task.compact`
- `task.logs.stream`
- `task.artifacts.list`
- `task.artifact.get`
- `memory.inspect`
- `skill.install`
- `config.get`

Not implemented:

- `task.cancel`

Client coverage:

- the CLI exposes command paths for the implemented inspection and control methods, including `reply`, `resume`, `memory`, `config`, and `skill-install`
- the TUI consumes `task.list`, `task.get`, `task.reply`, `task.resume`, artifact inspection, live event streams, approvals, diagnostics, memory inspection, and config inspection

Primary evidence:

- [models.py](/Users/jeastman/Projects/e/ecl-agent/packages/protocol/local_agent_protocol/models.py)
- [cli.py](/Users/jeastman/Projects/e/ecl-agent/apps/cli/local_agent_cli/cli.py)
- [protocol_client.py](/Users/jeastman/Projects/e/ecl-agent/apps/tui/local_agent_tui/protocol/protocol_client.py)
- [runtime_server.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/runtime_server.py)

### 4.8 Observability and Artifacting

**Observed implementation:** `Implemented` for the runtime baseline, `Partial` for broader operator UX

Implemented:

- append-only per-run event history
- persisted event store
- persisted diagnostics store
- persisted run metrics store
- persisted conversation-compaction store
- runtime-owned artifact registration
- artifact metadata listing plus preview retrieval
- CLI log/event rendering
- TUI timeline, artifact browser, markdown preview, approval queue, diagnostics, memory, and config views
- `memory.updated` and skill-install lifecycle events in the runtime event vocabulary

The skill-installation flow specifically adds:

- `skill.install.requested`
- `skill.install.validated`
- `skill.install.approval_requested`
- `skill.install.completed`
- `skill.install.failed`

Not yet implemented:

- web/operator visualization layer
- richer external tracing integrations

Primary evidence:

- [event_store.py](/Users/jeastman/Projects/e/ecl-agent/services/observability_service/local_agent_observability_service/event_store.py)
- [diagnostic_store.py](/Users/jeastman/Projects/e/ecl-agent/services/observability_service/local_agent_observability_service/diagnostic_store.py)
- [run_metrics_store.py](/Users/jeastman/Projects/e/ecl-agent/services/observability_service/local_agent_observability_service/run_metrics_store.py)
- [conversation_compaction_store.py](/Users/jeastman/Projects/e/ecl-agent/services/observability_service/local_agent_observability_service/conversation_compaction_store.py)
- [store.py](/Users/jeastman/Projects/e/ecl-agent/services/artifact_service/local_agent_artifact_service/store.py)

## 5. Verified Gaps and Live Regressions

These are the main gaps or regressions visible in the repository today:

1. `task.cancel` is still not implemented.
2. There is still no web client.
3. Memory retrieval precedence and richer governance semantics remain incomplete.
4. The current `pytest` run has 3 failures:
   - 2 runtime integration failures expecting persisted `subagent.started`
   - 1 TUI footer-hint expectation mismatch
5. The current `ruff` run reports 60 issues.

None of those gaps invalidate the section 28 architectural baseline. They do mean the repo should not be described as fully green or fully aligned with the long-range platform scope.

## 6. Bottom Line

The honest status today is:

- the repository satisfies the master spec's initial architecture baseline
- Milestones 0 through 3 are substantially implemented in code
- the repository has both a CLI and a local TUI client
- `task.compact` and `memory.updated` are implemented and should no longer be listed as missing
- the main unfinished work remains web-client/platform territory plus broader memory-governance maturity
- the current repository also has active test and lint regressions that should be tracked separately from architecture status

What is real today is a local-first agent runtime with:

- thin clients over a formal stdio protocol
- runtime-owned execution lifecycle
- a contained DeepAgent adapter
- governed filesystem and command execution
- durable checkpoints, approvals, diagnostics, metrics, event history, and compaction records
- explicit memory scopes with durable project memory
- restart recovery, resume, user-reply, and manual compaction support
- project-owned subagent roles with model routing and delegated execution
- governed skill installation into managed skill roots

What is not yet real today is the web client, cancellation, and the broader memory-governance maturity described in the long-range spec.
