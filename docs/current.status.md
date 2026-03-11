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
uv run pytest
uv run ruff check apps packages services tests
```

Observed results:

```text
87 passed in 1.02s
All checks passed!
```

## Executive Summary

The repository now implements the Milestone 0 and Milestone 1 vertical slice described by the master spec, and it has also delivered most of the Milestone 2 durable-runtime work:

- the monorepo has separate CLI and runtime applications
- the runtime exposes a transport-neutral JSON-RPC-style contract over stdio
- task execution responsibility resides in the runtime
- a project-owned `AgentHarness` boundary exists and a real DeepAgent-backed adapter is implemented
- filesystem and command access are mediated through a dedicated sandbox abstraction
- identity ingestion exists and is wired into runtime startup and prompt construction
- runtime event streaming and artifact registration exist

The repository does **not** yet implement most of the spec areas that are explicitly deferred beyond Milestone 2, but it now includes the Milestone 2 durability, governance, recovery, and inspection baseline:

- durable memory storage and inspection
- checkpoint metadata, thread registry, and checkpoint-backed pause/resume execution flow
- restart-time recovery of resumable runs
- `task.resume`, `task.approve`, `task.approvals.list`, `task.diagnostics.list`, `memory.inspect`, and `config.get` protocol support
- CLI support for approvals, diagnostics, approval decisions, resume, memory inspection, and redacted config inspection
- persistent event, diagnostic, and run-metric storage with restart-safe inspection
- runtime-owned policy engine, durable approval state, and run-scoped boundary grants

However, the repository still does **not** fully satisfy the master spec's initial architecture baseline as written.

The main remaining gaps against the spec are:

- the recommended future-client structure remains only partially realized (`apps/web`, `packages/sdk-client`, and `packages/sdk-runtime` do not exist)
- the protocol surface still omits `task.cancel`
- the event vocabulary still omits `memory.updated`
- richer web/operator observability beyond the runtime and CLI remains incomplete

The net result is:

- **Milestone 0:** implemented
- **Milestone 1:** implemented as a single-agent local runtime vertical slice
- **Milestone 2:** implemented as the durable, resumable, governed, and inspectable single-agent runtime baseline
- **Milestone 3:** implemented
- **Milestone 4 and later:** mostly not implemented

In master-spec terms, the repository is **substantially aligned** with the intended architecture, but it is **not yet fully compliant** with every acceptance item in section 28.

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
- `services/artifact_service`, `services/checkpoint_service`, `services/deepagent_runtime`, `services/memory_service`, `services/observability_service`, `services/policy_service`, `services/sandbox_service`, `services/subagent_registry`
- `agents/primary-agent/IDENTITY.md`
- `agents/subagents/*`
- `docs/adr`, `docs/specs`, `docs/plans`, `docs/architecture`

What does not exist from the recommended shape in the master spec:

- `apps/web`
- `packages/sdk-client`
- `packages/sdk-runtime`
- `agents/primary-agent/SYSTEM_PROMPT.md`
- `agents/primary-agent/skills/`

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
- `subagent.completed`
- `tool.called`
- `artifact.created`
- `task.completed`
- `task.failed`

Evidence:

- `EventType` enum in [packages/task_model/local_agent_task_model/models.py](/Users/jeastman/Projects/e/ecl-agent/packages/task_model/local_agent_task_model/models.py)
- event publishing in [apps/runtime/local_agent_runtime/task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py)
- tool events in [services/deepagent_runtime/local_agent_deepagent_runtime/tool_bindings.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/tool_bindings.py)

Specified by the master spec but not implemented:

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

**Observed implementation:** `Implemented` for the Milestone 3 runtime scope.

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

**Observed implementation:** `Partial`.

What exists:

- a runtime-owned `SubagentDefinition` / `SubagentAssetBundle` contract
- runtime-owned `ResolvedModelRoute`, `ResolvedToolBinding`, `ResolvedSubagentConfiguration`, and `SkillDescriptor` contracts
- a `SubagentRegistry` port and filesystem-backed registry implementation
- a runtime-owned `RuntimeModelResolver`
- a runtime-owned `RoleToolScopeResolver`
- a filesystem-backed role-local skill registry
- baseline role directories under `agents/subagents/` for planner, researcher, coder, verifier, and librarian
- manifest validation for role IDs, tool scopes, memory scopes, filesystem scopes, and optional assets
- runtime bootstrap composes and exposes resolved subagent inspection state
- `models.subagents.*` overrides are now consumed by runtime model resolution
- adapter compiles registry-loaded roles into live Deep Agent-native subagents
- role-specific prompt assembly happens inside the adapter
- runtime uses resolved role-local skills during execution
- role-specific tool scopes are wired into live adapter bindings
- `subagent.started` and `subagent.completed` events are emitted with runtime-owned payloads
- `TaskSnapshot.active_subagent` reflects the currently executing delegated role
- planner/researcher/coder/verifier/librarian definitions are available for Deep Agent-native delegation

What does not exist:

- richer multi-agent observability beyond lifecycle, tool, artifact, and plan events

Evidence:

- [subagents.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/subagents.py)
- [filesystem_subagent_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_registry/local_agent_subagent_registry/filesystem_subagent_registry.py)
- [tool_scope.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/tool_scope.py)
- [skill_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_registry.py)
- [deepagent_harness.py](/Users/jeastman/Projects/e/ecl-agent/services/deepagent_runtime/local_agent_deepagent_runtime/deepagent_harness.py)
- [task_runner.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/task_runner.py)
- [runtime.example.toml](/Users/jeastman/Projects/e/ecl-agent/docs/architecture/runtime.example.toml)

Assessment:

- The codebase now has the Phase 1 registry foundation plus the Phase 2 runtime-owned routing, tool governance, and skill discovery layer. Execution still behaves as a single-agent system until adapter compilation lands.

## 11. Model Routing

**Spec expectation:** runtime-owned model resolution for the primary agent and sub-agent roles, with inspectable and testable routing.

**Observed implementation:** `Partial`.

Implemented:

- config model supports `default_model`
- config model supports `subagent_model_overrides`
- runtime-owned `RuntimeModelResolver` resolves primary and subagent routes
- `subagent_model_overrides` are consumed with deterministic precedence
- runtime bootstrap exposes resolved per-role model inspection data

Not implemented:

- a separate `models.primary_agent` config path
- adapter use of per-role routes during live subagent execution

Evidence:

- [packages/config/local_agent_config/models.py](/Users/jeastman/Projects/e/ecl-agent/packages/config/local_agent_config/models.py)
- [packages/config/local_agent_config/loader.py](/Users/jeastman/Projects/e/ecl-agent/packages/config/local_agent_config/loader.py)
- [bootstrap.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/bootstrap.py)
- [model_routing.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/model_routing.py)

Assessment:

- Runtime-owned routing now exists and is inspectable, but execution still uses a single primary model until the adapter consumes those routes.

## 12. Skills

**Spec expectation:** project-owned skill directories for primary and sub-agents, runtime-owned discovery/loading/exposure.

**Observed implementation:** `Partial`.

Verified:

- there is no `skills/` directory under `agents/primary-agent`
- there are reserved `skills/` directories under `agents/subagents/*`
- runtime-owned role-local skill discovery exists for `agents/subagents/<role>/skills/`
- discovered skill descriptors are exposed in resolved subagent inspection state

Evidence:

- repository file listing under `agents/`
- [skill_registry.py](/Users/jeastman/Projects/e/ecl-agent/services/subagent_runtime/local_agent_subagent_runtime/skill_registry.py)
- [bootstrap.py](/Users/jeastman/Projects/e/ecl-agent/apps/runtime/local_agent_runtime/bootstrap.py)

Assessment:

- Skill support now exists as a minimal runtime-owned discovery layer for subagents only. Primary-agent skills and adapter-side skill use remain unfinished.

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

**Observed status:** `Implemented`.

Verified Milestone 2 deliverables:

- persistent service packages for checkpoints, memory, policy, and observability
- runtime-owned SQLite-backed seams for checkpoint metadata, thread bindings, approvals, memory records, persisted events, diagnostics, and run metrics
- persistence config and runtime bootstrap wiring
- pause/resume/approval-oriented run state extensions
- DeepAgent-side checkpoint adapter binding runtime-owned `thread_id` to framework-native checkpoint flows
- runtime-owned pause/resume lifecycle in `TaskRunner`
- `resume_service` and `recovery_service`
- restart recovery that reconstructs resumable runs from persisted events and checkpoint metadata
- durable memory CRUD plus promotion from `run_state` and `scratch` into `project`
- runtime-seeded inspectable identity memory records
- persistent event history, diagnostics, and run-metric inspection
- `task.resume`, `task.approve`, `task.approvals.list`, `task.diagnostics.list`, `memory.inspect`, and `config.get`
- CLI support for approvals, diagnostics, approval decisions, resume, memory inspection, and redacted config inspection

Explicitly deferred beyond Milestone 2:

- policy-driven artifact publishing rules
- retrieval precedence and richer memory policy semantics beyond current promotion/storage behavior

### 16.4 Milestone 3

**Observed status:** `Implemented`.

Implemented foundations:

- runtime-owned subagent asset contracts and filesystem registry
- baseline role assets under `agents/subagents/`
- manifest validation for role IDs and declared scopes
- runtime-owned per-role model routing, tool-scope resolution, and skill discovery
- adapter compilation of runtime-owned subagent definitions into native Deep Agent subagents
- live execution with role-scoped tools and primary-agent delegation through Deep Agent
- runtime-visible `subagent.started` and `subagent.completed` lifecycle projection
- `TaskSnapshot.active_subagent` tracking for live delegated execution

Still deferred beyond Milestone 3:

- richer multi-agent observability beyond current lifecycle/tool/plan/artifact events
- any future-client work deferred to Milestone 4+

### 16.5 Milestone 4

**Observed status:** `Not Implemented`

Absent:

- web client
- richer artifact browser
- live event visualization outside the CLI logs path

## 17. Acceptance Criteria Check Against the Master Spec

Master spec section 28 says the initial architecture baseline is satisfied when ten conditions hold. Current status:

- Fully implemented: 8 of 10
- Partially implemented: 2 of 10
- Not implemented: 0 of 10

Conclusion:

- The repository does **not yet** satisfy the master spec's initial architecture baseline in full.
- The remaining blockers are criterion 7 (separate model routing profiles for primary and sub-agents) and criterion 10 (codebase structure clearly supports future clients).

| Acceptance criterion | Status | Notes |
| --- | --- | --- |
| Distinct runtime and CLI applications exist | Implemented | `apps/runtime` and `apps/cli` are present and separate |
| Runtime exposes a transport-neutral protocol contract implemented over stdio | Implemented | JSON-RPC 2.0 over stdio is implemented |
| Task execution responsibility resides in the runtime | Implemented | `TaskRunner` owns execution flow |
| LangChain DeepAgent is isolated behind project-owned ports/adapters | Implemented | confined to `services/deepagent_runtime` |
| Memory taxonomy exists as explicit concepts in the codebase | Implemented | run-state, scratch, project, and identity memory concepts exist with durable storage and inspection |
| Sandbox/filesystem access is mediated by a dedicated abstraction | Implemented | `ExecutionSandbox`/`LocalExecutionSandbox` |
| Model routing supports separate profiles for primary and sub-agents | Partial | runtime-owned routing now exists, but adapter execution still uses the single primary model |
| `IDENTITY.md` ingestion exists as a runtime concern | Implemented | loaded at runtime startup and injected into prompts |
| Event streaming exists for task lifecycle visibility | Implemented | `task.logs.stream` plus runtime event envelopes |
| Codebase structure clearly supports future clients | Partial | shared contracts and runtime/client split support this, but no SDK or web client packages exist |

## 18. Concrete Gaps Relative to the Master Spec

These are the main verified gaps between the current implementation and the broader master spec:

1. Missing protocol method: `task.cancel`.
2. Missing event type: `memory.updated`.
3. No retrieval precedence or richer policy-governed memory behavior beyond current promotion/storage support.
4. CLI approval/config/memory inspection exists, but no richer web/operator inspection client exists.
5. No web client or client SDK packages.

## 19. Bottom Line

The repository currently implements a credible **Milestone 0 + Milestone 1 + Milestone 2 runtime baseline**, but it does **not** fully satisfy the master spec as written.

What is real today:

- a functioning local runtime/CLI architecture
- a formal protocol over stdio
- a runtime-owned task lifecycle
- a real DeepAgent-backed harness behind a project boundary
- a governed sandbox
- runtime-owned artifact registration
- event streaming and persisted task inspection
- identity ingestion
- durable memory and memory inspection
- approval-governed pause/resume with restart recovery
- persisted diagnostics and redacted config inspection

What remains future work relative to the master spec:

- separate runtime-owned model routing for primary and sub-agent roles
- sub-agents and role-based routing
- skills loading and adapter-side use of role-specific agent assets
- richer memory policy semantics
- cancellation
- additional clients

That makes the current codebase a strong single-agent governed runtime with durable Milestone 2 capabilities, while leaving several master-spec structural and multi-agent requirements explicitly unfinished.
