# Current Status: Implementation vs. Master Spec

This document compares the repository implementation to [local-agent-harness-master-spec-v1.md](/Users/jeastman/Projects/e/ecl-agent/docs/specs/local-agent-harness-master-spec-v1.md) based on direct verification of the current codebase on March 11, 2026.

It is intentionally implementation-first. Statements below are grounded in source files, repository structure, runtime configuration, and the current automated checks.

## Verification Basis

The comparison below was verified against:

- runtime code under `apps/runtime/local_agent_runtime`
- CLI code under `apps/cli/local_agent_cli`
- shared packages under `packages/*`
- service implementations under `services/*`
- agent assets under `agents/*`
- runtime example configuration at [runtime.example.toml](/Users/jeastman/Projects/e/ecl-agent/docs/architecture/runtime.example.toml)
- automated tests under `tests/*`

Verification commands executed in this workspace:

```bash
uv run pytest
uv run ruff check apps packages services tests
```

Observed results:

```text
136 passed in 1.30s
All checks passed!
```

## Executive Summary

The codebase now goes materially beyond the master spec's original stated scope of "foundational architecture and Milestone 0-1 guidance." The repository implements:

- the Milestone 0 foundation
- the Milestone 1 single-agent runtime slice
- the Milestone 2 durable/runtime-governance baseline
- the Milestone 3 sub-agent system baseline
- the runtime-governed `skill-installer` capability for controlled skill installation

The practical result is:

- the section 28 initial architecture baseline is satisfied
- Milestones 0, 1, 2, and 3 are substantially implemented
- Milestone 4 is still not implemented

The repo is not "done" relative to the entire master spec and surrounding follow-on ambitions. The main remaining gaps are in the future-client and richer-operator-experience space rather than the foundational runtime architecture.

## Status Legend

- `Implemented`: present in code and wired into runtime or CLI behavior
- `Partial`: some structures exist, but behavior is incomplete or narrower than the spec's broader intent
- `Not Implemented`: the spec calls for it, but the current repository does not implement it

## 1. Overall Standing Against the Master Spec

The master spec is best read in two layers:

1. the initial architecture baseline in section 28
2. the milestone roadmap in section 26

Against section 28, the repository is now in good shape. Against section 26, the repository has completed the first four roadmap stages through Milestone 3, with Milestone 4 still remaining.

That means the honest current position is:

- the foundational architecture is in place
- the durable-harness features expected after Milestone 1 are in place
- the sub-agent system expected in Milestone 3 is in place at a real execution level
- the multi-client platform work is still future work

## 2. Acceptance Criteria Check (Master Spec Section 28)

Master spec section 28 says the initial architecture baseline is satisfied when ten conditions hold.

Current status:

- `Implemented`: 10 of 10
- `Partial`: 0 of 10
- `Not Implemented`: 0 of 10

Conclusion:

- the repository now satisfies the master spec's initial architecture baseline

| Acceptance criterion | Status | Notes |
| --- | --- | --- |
| Distinct runtime and CLI applications exist | Implemented | `apps/runtime` and `apps/cli` are separate and have separate responsibilities |
| Runtime exposes a transport-neutral protocol contract implemented over stdio | Implemented | JSON-RPC 2.0 over stdio is implemented in the runtime server and CLI client |
| Task execution responsibility resides in the runtime | Implemented | `TaskRunner`, runtime handlers, and runtime server own task lifecycle and execution |
| LangChain DeepAgent is isolated behind project-owned ports/adapters | Implemented | DeepAgent usage is contained in `services/deepagent_runtime` behind the `AgentHarness` boundary |
| Memory taxonomy exists as explicit concepts in the codebase | Implemented | `run_state`, `project`, `identity`, and `scratch` exist as explicit runtime memory scopes |
| Sandbox/filesystem access is mediated by a dedicated abstraction | Implemented | `ExecutionSandbox`, `LocalExecutionSandboxFactory`, path policy, and command executor mediate access |
| Model routing supports separate profiles for primary and sub-agents | Implemented | runtime-owned model resolution exists for primary and sub-agent roles, and sub-agent compilation consumes those resolved routes |
| `IDENTITY.md` ingestion exists as a runtime concern | Implemented | identity loading, hashing/versioning, prompt injection, and identity-memory seeding all happen in runtime bootstrap |
| Event streaming exists for task lifecycle visibility | Implemented | runtime events are emitted, stored durably, and replayed via `task.logs.stream` |
| Codebase structure clearly supports future clients | Implemented | runtime/client split plus shared protocol/config/task packages provide the intended separation for future clients |

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
- thin CLI shell
- ADR pack under `docs/adr/`

### 3.2 Milestone 1

**Observed status:** `Implemented`

Verified deliverables:

- one primary DeepAgent behind the project-owned adapter boundary
- local controlled sandbox implementation
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
- SQLite-backed memory store under `services/memory_service`
- SQLite-backed approval, event, diagnostics, and metrics stores
- runtime recovery in [recovery_service.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/recovery_service.py)
- resume flow in [resume_service.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/resume_service.py)
- protocol/CLI support for `task.resume`, `task.approve`, `task.approvals.list`, `task.diagnostics.list`, `memory.inspect`, and `config.get`

### 3.4 Milestone 3

**Observed status:** `Implemented`

Verified deliverables:

- sub-agent registry
- role-based tool scopes
- model routing
- planner/researcher/coder/verifier flow baseline

Concrete implemented evidence includes:

- filesystem-backed registry in [filesystem_subagent_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_registry/local_agent_subagent_registry/filesystem_subagent_registry.py)
- role tool-scope resolution in [tool_scope.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/tool_scope.py)
- runtime-owned model routing in [model_routing.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/model_routing.py)
- adapter-side sub-agent compilation and execution in [deepagent_harness.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/deepagent_harness.py)
- runtime-owned skill installation, validation, and target resolution in [skill_installer.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_installer.py) and [skill_catalog.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_catalog.py)
- role assets under `agents/subagents/planner`, `researcher`, `coder`, `verifier`, and `librarian`
- runtime-visible `subagent.started` and `subagent.completed` events

Important nuance:

- the spec's milestone wording says "planner/researcher/coder/verifier flow"
- the implementation satisfies the architectural intent by providing real project-owned role definitions and Deep Agent-native delegation support
- it does not implement a bespoke hard-coded orchestration graph for those roles outside Deep Agent; the delegation remains agent-driven

This still counts as Milestone 3 implemented because the required runtime-owned role system, routing, scopes, and live execution path are present.

Additional implemented capability within this milestone band:

- the primary agent now receives a governed `skill-installer` tool
- the runtime exposes `skill.install`
- staged skills can be validated and installed into managed primary-agent or sub-agent skill roots
- skill installation is governed by runtime policy and approval flow
- installation emits events and artifacts and becomes visible to future runs through refreshed skill discovery

### 3.5 Milestone 4

**Observed status:** `Not Implemented`

Not present today:

- web client
- artifact browser
- live event visualization outside the CLI/log stream path

## 4. Architecture Areas

### 4.1 Runtime and CLI Separation

**Observed implementation:** `Implemented`

This is a strong match to the master spec. The runtime owns execution, lifecycle, artifacts, approvals, checkpoints, memory inspection, and event emission. The CLI remains a transport client and renderer.

Primary evidence:

- [task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py)
- [method_handlers.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/method_handlers.py)
- [runtime_server.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/runtime_server.py)
- [cli.py](/Users/jeastman/Projects/e/ecl-agent/apps/cli/local_agent_cli/cli.py)
- [client.py](/Users/jeastman/Projects/e/ecl-agent/apps/cli/local_agent_cli/client.py)

### 4.2 DeepAgent Containment

**Observed implementation:** `Implemented`

Direct DeepAgent and LangChain construction remains contained to the adapter layer. The rest of the runtime deals in project-owned request/result models and runtime-level events.

Primary evidence:

- [deepagent_harness.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/deepagent_harness.py)
- [tool_bindings.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/tool_bindings.py)

### 4.3 Memory Model

**Observed implementation:** `Implemented` for the section 28 baseline, `Partial` for the broader memory ambitions in sections 17 and 21

What is implemented:

- explicit memory scopes: `run_state`, `project`, `identity`, `scratch`
- durable SQLite-backed memory storage
- memory promotion from agent-writable scopes into project memory
- identity seeding into memory
- runtime inspection via `memory.inspect`

What remains incomplete relative to the broader spec language:

- richer retrieval precedence behavior is not yet implemented as a first-class runtime retrieval policy
- memory policy is still narrower than the spec's long-term intent

Primary evidence:

- [memory_promotion.py](/Users/jeastman/Projects/e/ecl-agent/services/memory_service/local_agent_memory_service/memory_promotion.py)
- [memory_store.py](/Users/jeastman/Projects/e/ecl-agent/services/memory_service/local_agent_memory_service/memory_store.py)
- [memory_seed.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/memory_seed.py)
- [method_handlers.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/method_handlers.py)

### 4.4 Sandbox and Filesystem Policy

**Observed implementation:** `Implemented`

The repo now clearly satisfies the spec's sandbox boundary requirements for the local-first runtime:

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

Identity is a real runtime concern, not a CLI concern. Policy and approvals are also runtime-owned and durable.

Implemented:

- `IDENTITY.md` loading, hashing, and versioning
- prompt construction using identity content
- durable approval storage
- runtime-owned policy decisions: `ALLOW`, `REQUIRE_APPROVAL`, `DENY`
- boundary-scoped approval grants
- approval-oriented pause/resume flow

Primary evidence:

- [loader.py](/Users/jeastman/Projects/e/ecl-agent/packages/identity/local_agent_identity/loader.py)
- [policy_engine.py](/Users/jeastman/Projects/e/ecl-agent/services/policy_service/local_agent_policy_service/policy_engine.py)
- [task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py)

### 4.6 Sub-Agents, Skills, and Model Routing

**Observed implementation:** `Implemented`, with some breadth still deferred

Implemented:

- filesystem-backed sub-agent registry
- role manifests and asset bundles
- role-scoped tools
- role-local skill discovery
- runtime-governed skill installation into managed primary-agent and sub-agent skill roots
- runtime-owned primary and sub-agent model resolution
- adapter-side compilation of runtime-owned roles into live Deep Agent-native sub-agents

Still narrower than the broadest possible reading of the spec:

- primary-agent skills are minimal compared to the sub-agent role setup
- observability around delegated execution is good enough for milestone status, but not yet rich operator telemetry

Primary evidence:

- [bootstrap.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/bootstrap.py)
- [filesystem_subagent_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_registry/local_agent_subagent_registry/filesystem_subagent_registry.py)
- [skill_catalog.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_catalog.py)
- [skill_installer.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_installer.py)
- [skill_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_registry.py)
- [model_routing.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/model_routing.py)
- [deepagent_harness.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/deepagent_harness.py)

### 4.7 Observability and Artifacting

**Observed implementation:** `Implemented` for the runtime baseline, `Partial` for richer future operator UX

Implemented:

- append-only per-run event history
- persisted event store
- persisted diagnostics store
- persisted run metrics store
- runtime-owned artifact registration
- CLI access to logs, diagnostics, approvals, config, memory inspection, and `skill.install`

The new skill-installation flow specifically adds:

- `skill.install.requested`, `skill.install.validated`, `skill.install.approval_requested`, `skill.install.completed`, and `skill.install.failed` runtime events
- validation report, install summary, file manifest, and conflict report artifacts for skill installation runs

Not yet implemented:

- richer trace integrations
- a web/operator visualization layer

Primary evidence:

- [event_store.py](/Users/jeastman/Projects/e/ecl-agent/services/observability_service/local_agent_observability_service/event_store.py)
- [diagnostic_store.py](/Users/jeastman/Projects/e/ecl-agent/services/observability_service/local_agent_observability_service/diagnostic_store.py)
- [run_metrics_store.py](/Users/jeastman/Projects/e/ecl-agent/services/observability_service/local_agent_observability_service/run_metrics_store.py)
- [store.py](/Users/jeastman/Projects/e/ecl-agent/services/artifact_service/local_agent_artifact_service/store.py)

## 5. Verified Gaps Relative to the Broader Spec and Follow-on Direction

These are the main remaining gaps after Milestone 3:

1. `task.cancel` is still not implemented.
2. `memory.updated` is still not part of the current event vocabulary.
3. Memory retrieval precedence and richer memory-governance semantics remain incomplete.
4. Milestone 4 multi-client work is not started in practice: no web client, artifact browser, or live event visualization UI.
5. The codebase supports future clients structurally, but the future-client packages suggested by the spec's recommended shape, such as SDK packages, do not exist yet.

None of those gaps invalidate the section 28 baseline. They do matter for the next stage of platform maturity.

## 6. Bottom Line

The honest status is:

- the repository now satisfies the master spec's initial architecture baseline
- Milestones 0 through 3 are substantially implemented in code, not just scaffolded
- the repo is stronger than the previous status document claimed
- the main unfinished work sits in Milestone 4 and in some richer policy/memory/operator UX areas

What is real today is a local-first agent runtime with:

- a thin CLI client over a formal stdio protocol
- a runtime-owned execution lifecycle
- a contained DeepAgent adapter
- governed filesystem and command execution
- durable checkpoints, approvals, diagnostics, and event history
- explicit memory scopes with durable project memory
- restart recovery and resume support
- project-owned sub-agent roles with model routing and delegated execution

What is not yet real today is the multi-client platform layer and some broader polish around cancellation, richer memory semantics, and operator-facing visualization.
