# Current Status: Implementation vs. Master Spec

This document compares the repository implementation to [local-agent-harness-master-spec-v1.md](/Users/jeastman/Projects/e/ecl-agent/docs/specs/local-agent-harness-master-spec-v1.md) based on direct verification of the current codebase.

It is intentionally implementation-first. Statements below are derived from source files, repository structure, configuration, and the current automated test suite. Nothing in this document is based on planned behavior alone.

## Verification Basis

The comparison below was verified against:

- runtime code under `apps/runtime/local_agent_runtime`
- CLI code under `apps/cli/local_agent_cli`
- shared packages under `packages/*`
- service implementations under `services/*`
- current agent assets under `agents/*`
- runtime example configuration at [runtime.example.toml](/Users/jeastman/Projects/e/ecl-agent/docs/architecture/runtime.example.toml)
- test suite under `tests/*`

Verification commands executed in this workspace:

```bash
.venv/bin/pytest
.venv/bin/ruff check apps packages services tests
```

Observed results:

```text
55 passed in 0.80s
All checks passed!
```

## Executive Summary

The repository now implements the Milestone 0 and Milestone 1 vertical slice described by the master spec:

- the monorepo has separate CLI and runtime applications
- the runtime exposes a transport-neutral JSON-RPC-style contract over stdio
- task execution responsibility resides in the runtime
- a project-owned `AgentHarness` boundary exists and a real DeepAgent-backed adapter is implemented
- filesystem and command access are mediated through a dedicated sandbox abstraction
- identity ingestion exists and is wired into runtime startup and prompt construction
- runtime event streaming and artifact registration exist

The repository does **not** yet implement most of the spec areas that are explicitly deferred beyond Milestone 1, but it now includes the Milestone 2 durability substrate plus Phase 5 inspection/config/CLI completion:

- durable memory/query contracts and storage seams
- checkpoint metadata and thread registry seams
- checkpoint-backed pause/resume execution flow
- restart-time recovery of resumable runs
- `task.resume`, `task.approve`, `task.approvals.list`, `task.diagnostics.list`, `memory.inspect`, and `config.get` protocol support
- CLI support for approvals, diagnostics, approval decisions, resume, memory inspection, and redacted config inspection
- persistent event/diagnostic/run-metrics storage with restart-safe inspection
- approval and policy storage seams
- task cancellation
- policy engine behavior beyond a placeholder runtime-owned boundary
- sub-agent registry and real multi-role orchestration
- model routing beyond a single default model plus unused config placeholders
- future clients such as web

The net result is:

- **Milestone 0:** implemented
- **Milestone 1:** implemented as a single-agent local runtime vertical slice
- **Milestone 2:** durable memory, approval-governed pause/resume, restart recovery, and inspection-oriented protocol/CLI surfaces implemented; some later-spec behaviors still incomplete
- **Milestone 3 and later:** mostly not implemented

## Status Legend

- `Implemented`: present in code and wired into runtime or CLI behavior
- `Partial`: some structures exist, but behavior is incomplete, placeholder-only, or not wired end to end
- `Not Implemented`: the spec calls for it, but the current repository does not implement it

## 1. Monorepo Structure and Top-Level Shape

**Spec expectation:** separate runtime and CLI apps, shared packages, runtime-facing services, agent assets, and documentation.

**Observed implementation:** `Implemented`, with some later-spec directories absent.

What exists:

- `apps/cli` with the user-facing CLI entrypoint and runtime client
- `apps/runtime` with runtime bootstrap, handlers, task runner, and stdio server
- `packages/config`, `packages/identity`, `packages/observability`, `packages/protocol`, `packages/task_model`
- `services/artifact_service`, `services/checkpoint_service`, `services/deepagent_runtime`, `services/memory_service`, `services/observability_service`, `services/policy_service`, `services/sandbox_service`
- `agents/primary-agent/IDENTITY.md`
- `docs/adr`, `docs/specs`, `docs/plans`, `docs/architecture`

What does not exist from the recommended shape in the master spec:

- `apps/web`
- `packages/sdk-client`
- `packages/sdk-runtime`
- `agents/subagents/*`
- `agents/primary-agent/SYSTEM_PROMPT.md`
- `agents/*/skills/`

Assessment:

- The core monorepo skeleton required for Milestone 0 and Milestone 1 is present.
- The broader future-oriented layout described in the master spec is only partially realized.

## 2. Runtime/Client Separation

**Spec expectation:** runtime owns execution, lifecycle, sandboxing, artifacts, memory semantics, and event production; CLI remains a thin client.

**Observed implementation:** `Implemented` for Milestone 1 scope.

Verified runtime ownership:

- `TaskRunner` in [task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py) creates task/run IDs, owns lifecycle transitions, invokes the harness, registers artifacts, and publishes events.
- `MethodHandlers` in [method_handlers.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/method_handlers.py) normalizes protocol calls into runtime behavior.
- `RuntimeServer` in [runtime_server.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/runtime_server.py) owns request dispatch and response/event emission.

Verified CLI thin-client behavior:

- [cli.py](/Users/jeastman/Projects/e/ecl-agent/apps/cli/local_agent_cli/cli.py) only parses commands, constructs JSON-RPC requests, and renders responses.
- [client.py](/Users/jeastman/Projects/e/ecl-agent/apps/cli/local_agent_cli/client.py) launches the runtime process, sends requests, and reads responses/events.
- The CLI does not create task IDs, run IDs, or artifact records and does not execute sandbox operations directly.

Assessment:

- This is one of the strongest spec alignments in the current implementation.

## 3. Technology Direction

**Spec expectation:** Python runtime, formal protocol, file-based configuration, CLI transport-neutral consumption.

**Observed implementation:** `Implemented`, with one spec item resolved by implementation choice.

Verified:

- runtime is Python
- CLI is also Python
- initial transport is JSON-RPC 2.0 over stdio
- configuration is TOML loaded by [loader.py](/Users/jeastman/Projects/e/ecl-agent/packages/config/local_agent_config/loader.py)

Important comparison detail:

- The master spec left CLI language as `TBD`.
- The implementation has concretely chosen Python for the CLI. This does not violate the spec because the spec did not mandate a different language; it only required that the CLI consume the formal runtime protocol rather than in-process bindings. The current CLI satisfies that rule.

## 4. Protocol Surface

### 4.1 Implemented methods

**Observed implementation:** `Partial` relative to the full master spec method list.

Implemented and wired end to end:

- `runtime.health`
- `task.create`
- `task.get`
- `task.approve`
- `task.approvals.list`
- `task.diagnostics.list`
- `task.resume`
- `task.logs.stream`
- `task.artifacts.list`
- `memory.inspect`
- `config.get`

Evidence:

- constants and request/result models in [packages/protocol/local_agent_protocol/models.py](/Users/jeastman/Projects/e/ecl-agent/packages/protocol/local_agent_protocol/models.py)
- dispatch in [apps/runtime/local_agent_runtime/runtime_server.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/runtime_server.py)
- CLI usage in [apps/cli/local_agent_cli/cli.py](/Users/jeastman/Projects/e/ecl-agent/apps/cli/local_agent_cli/cli.py)

Specified by the master spec but not implemented:

- `task.cancel`

Evidence of absence:

- no method constants or handler branches for `task.cancel` in the runtime or protocol package
- repository search returns only documentation references for `task.cancel`

### 4.2 Implemented event types

**Observed implementation:** `Partial` relative to the full master spec event list.

Implemented and emitted:

- `task.created`
- `task.started`
- `checkpoint.saved`
- `task.paused`
- `task.resumed`
- `approval.requested`
- `policy.denied`
- `recovery.discovered`
- `plan.updated`
- `subagent.started`
- `tool.called`
- `artifact.created`
- `task.completed`
- `task.failed`

Evidence:

- `EventType` enum in [packages/task_model/local_agent_task_model/models.py](/Users/jeastman/Projects/e/ecl-agent/packages/task_model/local_agent_task_model/models.py)
- event publishing in [apps/runtime/local_agent_runtime/task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py)
- tool events in [services/deepagent_runtime/local_agent_deepagent_runtime/tool_bindings.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/tool_bindings.py)

Specified by the master spec but not implemented:

- `subagent.completed`
- `memory.updated`

### 4.3 Envelope shape and correlation

**Observed implementation:** `Implemented` for the currently supported methods/events.

Verified:

- JSON-RPC request/response models exist
- `correlation_id` is supported in request and response envelopes
- runtime events use a dedicated `"type": "runtime.event"` envelope with `protocol_version`
- events carry `event_id`, `event_type`, `timestamp`, `task_id`, `run_id`, `correlation_id`, `source`, and `payload`

Evidence:

- [packages/protocol/local_agent_protocol/models.py](/Users/jeastman/Projects/e/ecl-agent/packages/protocol/local_agent_protocol/models.py)
- [apps/runtime/local_agent_runtime/runtime_server.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/runtime_server.py)

Assessment:

- The implemented protocol is narrower than the master spec, but the portions that exist follow the spec’s envelope and transport direction closely.

## 5. Task Model and Lifecycle

**Spec expectation:** explicit task contracts, normalization, lifecycle states, and runtime-owned snapshots.

**Observed implementation:** `Partial`, with Milestone 1 scope implemented.

Implemented request/task fields:

- `objective`
- `workspace_roots`
- `scope`
- `success_criteria`
- `constraints`
- `allowed_capabilities`
- `metadata`

Not implemented in the task create contract:

- `approval_policy`
- `identity_bundle_version/reference`

Implemented lifecycle/status concepts:

- `created`
- `accepted`
- `planning`
- `executing`
- `paused`
- `awaiting_approval`
- `completed`
- `failed`

Not implemented:

- `resuming`
- `cancelled`

Important implementation detail:

- `TaskStatus` defines `CREATED`, `ACCEPTED`, `PLANNING`, `EXECUTING`, `PAUSED`, `AWAITING_APPROVAL`, `COMPLETED`, and `FAILED`.
- `RunState` is initially created with `ACCEPTED`.
- `task.created` is emitted as an event payload/status rather than persisted as the authoritative stored status.
- planning is represented through `current_phase` updates and `plan.updated` events, not a durable top-level `TaskStatus.PLANNING` transition.
- `RunState` and `TaskSnapshot` now include resumability and approval-oriented fields such as `awaiting_approval`, `pending_approval_id`, `is_resumable`, `pause_reason`, `checkpoint_thread_id`, and `latest_checkpoint_id`.
- paused runs are resumed through the explicit `task.resume` runtime path rather than by reissuing `task.create`.

Evidence:

- [packages/task_model/local_agent_task_model/models.py](/Users/jeastman/Projects/e/ecl-agent/packages/task_model/local_agent_task_model/models.py)
- [apps/runtime/local_agent_runtime/task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py)
- [packages/protocol/local_agent_protocol/models.py](/Users/jeastman/Projects/e/ecl-agent/packages/protocol/local_agent_protocol/models.py)

Assessment:

- The task model still does not implement the full future lifecycle, but it now includes the Phase 1 state extensions plus the Phase 2 runtime-backed pause/resume lifecycle.

## 6. DeepAgent Adapter Boundary

**Spec expectation:** project-owned ports with framework containment; only adapter layer may directly construct DeepAgent/LangChain objects.

**Observed implementation:** `Implemented` for the current single-agent slice.

Verified:

- `AgentHarness` protocol is defined in the runtime layer
- concrete implementation is `LangChainDeepAgentHarness`
- `deepagents.create_deep_agent` and `langchain.chat_models.init_chat_model` are only used inside [deepagent_harness.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/deepagent_harness.py)
- sandbox-backed LangChain tools are created inside [tool_bindings.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/tool_bindings.py)
- runtime receives plain project-owned request/result dataclasses and runtime-friendly callback events

Not implemented from the broader spec:

- `ModelResolver`
- `SubAgentRegistry`
- `PolicyEngine`
- real role-based sub-agent composition

Assessment:

- Framework containment is real and explicit.
- The broader adapter ecosystem described in the master spec is not yet present.

## 7. Sandbox and Filesystem Policy

**Spec expectation:** governed workspace, scratch, and memory zones; normalized paths; sandbox-mediated commands and file access; no unrestricted host access.

**Observed implementation:** `Implemented` for local Milestone 1 behavior.

Verified capabilities:

- three zones exist: `workspace`, `scratch`, `memory`
- all paths are normalized through `normalize_sandbox_path`
- path traversal using `..` is rejected
- absolute sandbox paths are rejected
- filesystem reads and writes go through `LocalExecutionSandbox`
- command execution goes through `CommandExecutor`
- artifact path materialization is derived from sandbox-visible paths

Important implementation details:

- workspace access is rooted to the first allowed workspace root for file operations
- command execution can only use a governed zone path as `cwd`
- `WorkspaceManager` creates `scratch/<task>/<run>` and `memory/<task>` under the runtime root
- `memory` zone exists structurally, but no durable memory service is built on top of it

Evidence:

- [path_policy.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/path_policy.py)
- [workspace_manager.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/workspace_manager.py)
- [sandbox.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/sandbox.py)
- [command_executor.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/command_executor.py)
- sandbox tests in [test_local_execution_sandbox.py](/Users/jeastman/Projects/e/ecl-agent/tests/unit/test_local_execution_sandbox.py) and [test_sandbox_path_policy.py](/Users/jeastman/Projects/e/ecl-agent/tests/unit/test_sandbox_path_policy.py)

Assessment:

- The local sandbox abstraction is present and enforced.
- Remote/provider-backed sandbox support is not implemented.

## 8. Memory Model

**Spec expectation:** explicit taxonomy covering run state memory, project memory, identity/policy memory, and ephemeral scratch memory, with durable memory support as part of the initial implementation guidance.

**Observed implementation:** `Partial`, heavily biased to run-local state only.

Implemented:

- run-local state via `InMemoryRunStateStore`
- identity ingestion via `IdentityBundle`
- ephemeral scratch filesystem zone via sandbox roots
- memory filesystem zone creation under the runtime root
- durable memory record model and SQLite-backed `MemoryStore` seam under `services/memory_service`

Not implemented:

- memory retrieval precedence logic
- policy-governed promotion decisions

Important nuance:

- The master spec’s section 17.3 says the initial implementation should support project memory via a durable store-backed abstraction.
- The current repository does not implement that. The implementation aligns with the narrower Milestone 1 planning docs instead of the more forward-looking wording in the master spec.

Evidence:

- [run_state_store.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/run_state_store.py)
- [memory_models.py](/Users/jeastman/Projects/e/ecl-agent/services/memory_service/local_agent_memory_service/memory_models.py)
- [memory_store.py](/Users/jeastman/Projects/e/ecl-agent/services/memory_service/local_agent_memory_service/memory_store.py)
- runtime-facing `memory.inspect` models and handler path in the protocol/runtime packages

Assessment:

- Memory taxonomy now exists in code shape with durable storage, explicit promotion mechanics, identity inspection seeding, and runtime inspection support, but retrieval precedence and policy-governed promotion remain unfinished.

## 9. Identity and Policy

**Spec expectation:** identity bundle loading, controlled policy/config inputs, policy influence on prompt construction, tool exposure, sandbox access, memory persistence, and approvals.

**Observed implementation:** `Partial`.

Implemented:

- identity document loading and validation
- SHA-256 based identity version/hash generation
- identity content injected into system prompt construction
- config model contains a `policy` table
- config model contains a dedicated `persistence` section
- task request may carry `allowed_capabilities`
- tool bindings enforce `allowed_capabilities` if provided
- runtime bootstrap now composes a runtime-owned `PolicyEngine`, durable `ApprovalStore`, and run-scoped `BoundaryGrantStore`
- runtime policy now classifies governed operations as `ALLOW`, `REQUIRE_APPROVAL`, or `DENY`
- approval requests are persisted durably and runs transition into and out of `awaiting_approval`
- `task.approve` records approval decisions and resumes approved runs through the runtime-owned resume path
- denied actions emit `policy.denied` plus structured diagnostics instead of creating resumable success paths

Not implemented:

- policy-driven memory rules
- policy-driven artifact publishing rules

Important implementation detail:

- The `[policy]` table from [runtime.example.toml](/Users/jeastman/Projects/e/ecl-agent/docs/architecture/runtime.example.toml) is loaded into `RuntimeConfig.policy`.
- The `[persistence]` table is loaded into `RuntimeConfig.persistence` and used by runtime bootstrap to compose SQLite-backed durable stores.
- Runtime policy enforcement now governs sandbox-backed writes and command execution through runtime-owned operation classification, boundary approvals, and deny handling.
- Policy configuration currently narrows command-class allow/deny tiers, while memory promotion and artifact publishing rules remain future work.

Evidence:

- [packages/identity/local_agent_identity/loader.py](/Users/jeastman/Projects/e/ecl-agent/packages/identity/local_agent_identity/loader.py)
- [packages/config/local_agent_config/models.py](/Users/jeastman/Projects/e/ecl-agent/packages/config/local_agent_config/models.py)
- [packages/config/local_agent_config/loader.py](/Users/jeastman/Projects/e/ecl-agent/packages/config/local_agent_config/loader.py)
- [tool_bindings.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/tool_bindings.py)

Assessment:

- Identity is implemented as a real runtime concern.
- Policy and approvals are now implemented as runtime-owned behavior for governed file and command operations, with durable approval state and restart-safe recovery.

## 10. Sub-Agent Strategy

**Spec expectation:** explicit roles such as Planner, Researcher, Coder, Verifier, and Librarian; role-specific tools, model profiles, prompts, and observability.

**Observed implementation:** `Not Implemented` as a real subsystem, with one minimal placeholder signal.

What exists:

- `subagent.started` events are emitted
- the adapter synthesizes a single role `"primary"` with name `"repo-summarizer"`
- `TaskSnapshot.active_subagent` can store the current role
- config can parse `models.subagents.*`

What does not exist:

- sub-agent registry
- multiple role directories under `agents/subagents/`
- role-specific tool scopes
- role-specific prompts or overlays
- subagent completion events
- planner/researcher/coder/verifier/librarian execution flow

Evidence:

- [deepagent_harness.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/deepagent_harness.py)
- [task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py)
- [runtime.example.toml](/Users/jeastman/Projects/e/ecl-agent/docs/architecture/runtime.example.toml)

Assessment:

- The codebase exposes a small amount of vocabulary for sub-agents, but the actual sub-agent system described by the master spec has not been built.

## 11. Model Routing

**Spec expectation:** runtime-owned model resolution for the primary agent and sub-agent roles, with inspectable and testable routing.

**Observed implementation:** `Partial`.

Implemented:

- config model supports `default_model`
- config model supports `subagent_model_overrides`
- runtime bootstrap uses `config.default_model.provider` and `config.default_model.model`

Not implemented:

- any model resolver abstraction
- runtime use of `subagent_model_overrides`
- per-role model routing
- inspection or exposure of resolved routing

Evidence:

- [packages/config/local_agent_config/models.py](/Users/jeastman/Projects/e/ecl-agent/packages/config/local_agent_config/models.py)
- [packages/config/local_agent_config/loader.py](/Users/jeastman/Projects/e/ecl-agent/packages/config/local_agent_config/loader.py)
- [bootstrap.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/bootstrap.py)

Assessment:

- The config shape anticipates model routing, but the runtime currently behaves as a single-model system.

## 12. Skills

**Spec expectation:** project-owned skill directories for primary and sub-agents, runtime-owned discovery/loading/exposure.

**Observed implementation:** `Not Implemented`.

Verified:

- there is no `skills/` directory under `agents/primary-agent`
- there are no `agents/subagents/*` directories
- there is no skill loader or skill registry in runtime or services code

Evidence:

- repository file listing under `agents/`
- absence of skill-related runtime code

## 13. Observability and Eventing

**Spec expectation:** append-only run event streams, structured logs, correlation-aware events, trace-friendly metadata, operational debugging support.

**Observed implementation:** `Partial`, with solid Milestone 1 eventing and lightweight observability.

Implemented:

- in-memory append-only event bus per run
- correlated runtime events with timestamps and source metadata
- SQLite-backed persistent `EventStore`
- SQLite-backed persistent `DiagnosticStore`
- SQLite-backed persistent `RunMetricsStore`
- stderr log emission via `log_record`
- stderr event emission via `emit_event`
- `task.logs.stream` history replay

Not implemented:

- tracing integrations
- explicit run trace model
- richer diagnostics pipeline beyond foundational durable records

Evidence:

- [event_bus.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/event_bus.py)
- [logging.py](/Users/jeastman/Projects/e/ecl-agent/packages/observability/local_agent_observability/logging.py)
- [method_handlers.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/method_handlers.py)

Assessment:

- Eventing is implemented and central to the runtime.
- Persistent event history, diagnostics, and richer run metrics now support restart-safe inspection, but higher-level tracing and deeper diagnostics remain minimal.

## 14. Artifact Model

**Spec expectation:** runtime-owned first-class artifacts with metadata including artifact ID, task/run IDs, logical path, source role, content type, timestamp, and persistence class.

**Observed implementation:** `Implemented` for Milestone 1 scope.

Implemented metadata fields:

- `artifact_id`
- `task_id`
- `run_id`
- `logical_path`
- `content_type`
- `created_at`
- `persistence_class`
- `source_role`
- `source_tool`
- `byte_size`
- `display_name`
- `summary`
- `hash`

Important implementation details:

- artifacts are registered by the runtime after the harness returns sandbox paths
- workspace artifacts map to logical paths relative to the workspace root
- scratch and memory artifacts keep zone-prefixed logical paths
- persistence class defaults by zone:
  - workspace -> `run`
  - scratch -> `ephemeral`
  - memory -> `project`

Evidence:

- [services/artifact_service/local_agent_artifact_service/store.py](/Users/jeastman/Projects/e/ecl-agent/services/artifact_service/local_agent_artifact_service/store.py)
- [services/sandbox_service/local_agent_sandbox_service/sandbox.py](/Users/jeastman/Projects/e/ecl-agent/services/sandbox_service/local_agent_sandbox_service/sandbox.py)
- artifact tests in [test_artifact_store.py](/Users/jeastman/Projects/e/ecl-agent/tests/unit/test_artifact_store.py)

Assessment:

- Artifact ownership and metadata are strongly aligned with the master spec.

## 15. Security and Safety Position

**Spec expectation:** governed interfaces, no raw host exposure, runtime-owned policy enforcement, approval-ready design, and sandbox mediation.

**Observed implementation:** `Partial`.

Implemented:

- no direct CLI filesystem execution path
- sandbox path normalization and rooted access checks
- command execution only through sandbox API
- adapter uses project-owned sandbox tools instead of DeepAgent’s built-in filesystem backend

Not implemented:

- approval-ready execution control in the runtime
- dedicated policy engine
- secrets handling strategy beyond not exposing a raw host interface

Assessment:

- The repository has real sandbox and boundary discipline.
- The broader safety and policy apparatus described for the future platform is not yet present.

## 16. Milestone Status vs. Master Spec

### 16.1 Milestone 0

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

### 16.2 Milestone 1

**Observed status:** `Implemented`

Verified deliverables:

- one primary DeepAgent through the adapter boundary
- local controlled sandbox implementation
- basic task execution
- event streaming
- artifact capture
- run-local memory/state

### 16.3 Milestone 2

**Observed status:** `Partial`.

Implemented in Phase 1 and Phase 2:

- persistent service packages for checkpoints, memory, policy, and observability
- runtime-owned SQLite-backed seams for checkpoint metadata, thread bindings, approvals, memory records, persisted events, diagnostics, and run metrics
- persistence config and runtime bootstrap wiring
- pause/resume/approval-oriented run state extensions
- DeepAgent-side checkpoint adapter binding runtime-owned `thread_id` to framework-native checkpoint flows
- runtime-owned pause/resume lifecycle in `TaskRunner`
- `resume_service` and `recovery_service`
- restart recovery that reconstructs resumable runs from persisted events and checkpoint metadata
- `task.resume` protocol plumbing and minimal CLI support

Implemented in Phase 3:

- durable memory CRUD plus promotion from `run_state` and `scratch` into `project`
- runtime-seeded inspectable identity memory records
- `memory.inspect` protocol plumbing and runtime handler support

Still absent or incomplete:

- richer observability behavior on top of the new stores
- CLI memory inspection support
- policy-governed memory promotion and artifact publishing rules

### 16.4 Milestone 3

**Observed status:** `Not Implemented`, except for placeholder config/event vocabulary.

Absent:

- sub-agent registry
- role-based tool scopes
- model routing by role
- planner/researcher/coder/verifier flow

### 16.5 Milestone 4

**Observed status:** `Not Implemented`

Absent:

- web client
- richer artifact browser
- live event visualization outside the CLI logs path

## 17. Acceptance Criteria Check Against the Master Spec

Master spec section 28 says the initial architecture baseline is satisfied when ten conditions hold. Current status:

| Acceptance criterion | Status | Notes |
| --- | --- | --- |
| Distinct runtime and CLI applications exist | Implemented | `apps/runtime` and `apps/cli` are present and separate |
| Runtime exposes a transport-neutral protocol contract implemented over stdio | Implemented | JSON-RPC 2.0 over stdio is implemented |
| Task execution responsibility resides in the runtime | Implemented | `TaskRunner` owns execution flow |
| LangChain DeepAgent is isolated behind project-owned ports/adapters | Implemented | confined to `services/deepagent_runtime` |
| Memory taxonomy exists as explicit concepts in the codebase | Partial | run-local and identity exist; project memory and promotion logic do not |
| Sandbox/filesystem access is mediated by a dedicated abstraction | Implemented | `ExecutionSandbox`/`LocalExecutionSandbox` |
| Model routing supports separate profiles for primary and sub-agents | Partial | config parses subagent overrides, runtime does not use them |
| `IDENTITY.md` ingestion exists as a runtime concern | Implemented | loaded at runtime startup and injected into prompts |
| Event streaming exists for task lifecycle visibility | Implemented | `task.logs.stream` plus runtime event envelopes |
| Codebase structure clearly supports future clients | Partial | shared contracts and runtime/client split support this, but no SDK or web client packages exist |

## 18. Concrete Gaps Relative to the Master Spec

These are the main verified gaps between the current implementation and the broader master spec:

1. Missing protocol method: `task.cancel`.
2. Missing event types: `subagent.completed`, `memory.updated`.
3. No retrieval precedence or policy-governed promotion behavior for durable memory yet.
4. CLI approval/config/memory inspection exists, but no richer web/operator inspection client exists.
5. No sub-agent registry or multi-role orchestration.
6. No actual use of `subagent_model_overrides` for model routing.
7. No skill discovery or loading subsystem.
8. No web client or client SDK packages.

## 19. Bottom Line

The repository currently satisfies the master spec as a **Milestone 0 + Milestone 1 implementation**, not as a full realization of the entire future platform described across the rest of the document.

What is real today:

- a functioning local runtime/CLI architecture
- a formal protocol over stdio
- a runtime-owned task lifecycle
- a real DeepAgent-backed harness behind a project boundary
- a governed sandbox
- runtime-owned artifact registration
- event streaming and task inspection
- identity ingestion

What remains future work relative to the master spec:

- approvals
- durable memory
- policy engine behavior
- sub-agents and role-based routing
- memory/config inspection
- cancellation/resumption
- additional clients

That makes the current codebase a credible implementation of the first vertical slice envisioned by the master spec, while leaving the post-Milestone-1 platform capabilities explicitly unfinished.
