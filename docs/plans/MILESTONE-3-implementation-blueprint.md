# MILESTONE-3 Implementation Blueprint

Deep Agent Native Subagent Integration

This blueprint translates the Milestone-3 specification into an implementation plan for the current codebase. It is grounded in the project’s present state: Milestone-2 is complete, subagent support is still largely absent, config already anticipates subagent model overrides, `subagent.started` exists as a placeholder, and the DeepAgent adapter remains properly isolated behind project-owned ports.

The key architectural constraint for this milestone is that the project must **use LangChain Deep Agent’s native subagent mechanism**, while preserving the project’s own bounded concepts, runtime ownership, and adapter containment. The runtime owns role definitions, policy, model routing, tool scoping, and observability; the adapter compiles those definitions into Deep Agent-native subagents. This preserves the Triadic Lens and respects the existing architecture and ADR direction.

---

## 1. Milestone Intent

Milestone-3 is complete when the runtime can:

* load project-owned subagent role definitions
* resolve model assignments per role
* bind only allowed tools per role
* attach role-specific skills and prompt assets
* compile those roles into Deep Agent-native subagents inside the adapter
* emit real subagent lifecycle events during execution

It must **not** introduce a custom runtime-owned delegation engine that bypasses or duplicates Deep Agent’s own subagent/task mechanism. The master spec calls for a sub-agent system with role-based tool scopes and model routing, and the current status shows those capabilities remain unfinished.

---

## 2. Implementation Strategy

Build Milestone-3 in four slices:

### Slice A — Project-owned subagent assets and registry

Create the filesystem conventions, domain models, and registry that describe subagents in project terms.

### Slice B — Model routing, tool scoping, and skill discovery

Add the runtime services that resolve each role’s model, tools, and skills without exposing LangChain types.

### Slice C — Deep Agent adapter compilation

Teach `LangChainDeepAgentHarness` to convert project-owned subagent definitions into native Deep Agent subagent configuration.

### Slice D — Eventing and verification

Emit `subagent.completed`, enrich `subagent.started`, and validate the end-to-end runtime behavior with focused integration tests.

This order keeps the architecture clean and reduces the risk of framework leakage.

---

## 3. Target Architecture After Milestone-3

The effective flow should be:

```text
TaskRunner
  -> AgentHarness
      -> LangChainDeepAgentHarness
          -> primary Deep Agent
          -> compiled Deep Agent subagents
              <- project-owned SubagentDefinitionRegistry
              <- ModelResolver
              <- RoleToolScopeResolver
              <- SkillRegistry / asset loader
```

The runtime still owns task lifecycle, sandbox, approvals, memory, and eventing. The adapter remains the only layer allowed to touch Deep Agent construction APIs. That boundary is already a real architectural property of the project and must remain so.

---

## 4. Blueprint Scope

This blueprint covers:

* runtime domain models for subagents
* registry and asset loading
* model resolution
* per-role tool binding
* adapter compilation into Deep Agent subagents
* lifecycle event projection
* tests and QA criteria

This blueprint does **not** cover:

* custom orchestration loops outside Deep Agent
* skill authoring UX
* web client work
* memory policy enhancements beyond what is needed to express role scopes
* task cancellation
* advanced distributed execution

Those remain outside Milestone-3.

---

## 5. Deliverables

Milestone-3 should produce the following concrete deliverables.

### Runtime/domain deliverables

* `SubagentDefinition` model
* `SubagentAssetBundle` model
* `SubagentRegistry` port and filesystem-backed implementation
* `ModelResolver` implementation
* `RoleToolScopeResolver`
* initial `SkillRegistry` or skill loader slice sufficient for subagent-local skills

### Adapter deliverables

* updated `LangChainDeepAgentHarness` that accepts subagent definitions
* compilation of runtime definitions into Deep Agent-native subagents
* projection of Deep Agent subagent activity into runtime event envelopes

### Repo structure deliverables

* `agents/subagents/planner/`
* `agents/subagents/researcher/`
* `agents/subagents/coder/`
* `agents/subagents/verifier/`
* `agents/subagents/librarian/`

### Event deliverables

* `subagent.started`
* `subagent.completed`

The protocol already anticipates both lifecycle events, but the current implementation only partially supports the first and lacks the second.

---

## 6. Files and Packages to Add or Update

Below is the recommended implementation footprint, using the current monorepo shape as guidance.

### Add under `agents/`

```text
agents/
  subagents/
    planner/
      IDENTITY.md
      SYSTEM_PROMPT.md
      manifest.yaml
      skills/
    researcher/
      IDENTITY.md
      SYSTEM_PROMPT.md
      manifest.yaml
      skills/
    coder/
      IDENTITY.md
      SYSTEM_PROMPT.md
      manifest.yaml
      skills/
    verifier/
      IDENTITY.md
      SYSTEM_PROMPT.md
      manifest.yaml
      skills/
    librarian/
      IDENTITY.md
      SYSTEM_PROMPT.md
      manifest.yaml
      skills/
```

### Add in runtime/domain-oriented packages or services

Recommended new modules:

```text
packages/agent_runtime/
  models/
    subagents.py
  ports/
    subagent_registry.py
    model_resolver.py
    skill_registry.py
  services/
    role_tool_scope_resolver.py

services/agent_assets/
  filesystem_subagent_registry.py
  filesystem_skill_registry.py

services/deepagent_runtime/
  local_agent_deepagent_runtime/
    deepagent_harness.py          # update
    subagent_compiler.py          # new
    tool_bindings.py              # update
    deepagent_events.py           # new or expanded
```

If you prefer to stay closer to the current package naming style, the exact path names may vary. The important part is the dependency direction: runtime uses ports; infrastructure implements them.

---

## 7. Domain Model Design

### 7.1 `SubagentDefinition`

Create a project-owned model that contains only runtime concepts.

Recommended fields:

```python
@dataclass(frozen=True)
class SubagentDefinition:
    role_id: str
    name: str
    description: str
    model_profile: str | None
    tool_scope: tuple[str, ...]
    memory_scope: tuple[str, ...]
    filesystem_scope: tuple[str, ...]
    identity_path: Path | None
    system_prompt_path: Path | None
    skills_path: Path | None
```

This model should be free of LangChain and Deep Agent types.

### 7.2 `SubagentAssetBundle`

If the registry does parsing and file loading, keep the loaded asset content separate from the lightweight definition.

Recommended fields:

```python
@dataclass(frozen=True)
class SubagentAssetBundle:
    definition: SubagentDefinition
    identity_text: str
    system_prompt_text: str
    skill_descriptors: tuple[SkillDescriptor, ...]
```

### 7.3 `SkillDescriptor`

If the project does not already have a stable skill descriptor type, introduce a narrow one now. It should be enough to carry skill metadata into the adapter without locking in an overbuilt skill subsystem.

---

## 8. Registry and Asset Loading

### 8.1 Introduce a `SubagentRegistry` port

The architecture already anticipates a `SubAgentRegistry` as a runtime port.

Recommended interface:

```python
class SubagentRegistry(Protocol):
    def list_roles(self) -> list[str]: ...
    def get_definition(self, role_id: str) -> SubagentDefinition: ...
    def get_asset_bundle(self, role_id: str) -> SubagentAssetBundle: ...
    def list_asset_bundles(self) -> list[SubagentAssetBundle]: ...
```

### 8.2 Implement `FileSystemSubagentRegistry`

This implementation should:

* load subagent directories from `agents/subagents/`
* require `manifest.yaml`
* optionally load `IDENTITY.md`
* optionally load `SYSTEM_PROMPT.md`
* discover skills under `skills/`

### 8.3 `manifest.yaml` shape

Use a narrow, explicit manifest.

Suggested initial schema:

```yaml
role_id: planner
name: Planner
description: Break objectives into milestones and maintain execution structure.
model_profile: planner
tool_scope:
  - read_files
  - memory_lookup
  - plan_update
memory_scope:
  - run
  - project
filesystem_scope:
  - workspace
  - memory
```

Do not put raw LangChain configuration in the manifest. Keep it project-owned.

### 8.4 Validation rules

Registry load should fail fast if:

* `role_id` is missing
* role directory name and `role_id` conflict
* duplicate roles exist
* `tool_scope` contains unknown tool identifiers
* asset files are unreadable
* skills fail basic discovery validation

---

## 9. Model Routing

The current config already supports separate subagent model overrides, but the runtime does not use them yet.

### 9.1 Implement `ModelResolver`

Recommended interface:

```python
class ModelResolver(Protocol):
    def resolve_primary(self) -> ResolvedModelRoute: ...
    def resolve_subagent(self, role_id: str, model_profile: str | None) -> ResolvedModelRoute: ...
```

### 9.2 Resolution order

Implement the resolution behavior described in the spec:

1. project override for the named subagent profile
2. subagent-declared `model_profile`
3. primary/default runtime model
4. default model

This aligns with both the status gap and ADR-0006’s intent that model routing be runtime-owned and inspectable.

### 9.3 Resolved route object

Return a small project-owned object:

```python
@dataclass(frozen=True)
class ResolvedModelRoute:
    provider: str
    model: str
    profile_name: str
    source: str
```

This gives you a stable object for diagnostics, testing, and event metadata.

---

## 10. Role Tool Scope Resolution

The architecture and ADRs both call for explicit per-role tool boundaries.

### 10.1 Introduce `RoleToolScopeResolver`

This component takes:

* subagent definition
* runtime policy state
* task/request capability grants
* current sandbox/memory adapters

and returns the exact tool set allowed for that role.

Recommended interface:

```python
class RoleToolScopeResolver:
    def resolve_tools(
        self,
        role: SubagentDefinition,
        task_context: TaskExecutionContext,
    ) -> list[ProjectToolBinding]:
        ...
```

### 10.2 Tool identifiers

Create or normalize stable internal tool IDs such as:

* `read_files`
* `write_files`
* `execute_commands`
* `memory_lookup`
* `memory_promote`
* `plan_update`
* `artifact_inspect`

These identifiers belong to the runtime vocabulary, not LangChain.

### 10.3 Policy enforcement

Tool resolution must remain policy-aware. Policy is already a runtime concern and governs file and command operations. Milestone-3 must continue that pattern instead of letting subagents bypass it.

---

## 11. Skill Discovery and Loading

The master spec places skills under project-owned directories for both the primary agent and subagents.

### 11.1 Milestone-3 skill scope

Do only the minimum needed:

* discover skill directories
* parse enough metadata to identify valid skills
* attach role-local skills to that role during adapter compilation

Do not implement full skill authoring or generation flows in this milestone.

### 11.2 Recommended loader behavior

For each `agents/subagents/<role>/skills/` directory:

* discover valid skill folders/files
* return `SkillDescriptor` entries
* surface loader errors clearly
* keep the descriptor independent from Deep Agent types

### 11.3 Compatibility goal

The loader should anticipate `agentskills.io` alignment, but the project-owned descriptor should remain framework-neutral.

---

## 12. Deep Agent Adapter Compilation

This is the most important implementation slice.

### 12.1 Update `LangChainDeepAgentHarness`

It already encapsulates `deepagents.create_deep_agent` and model construction inside the adapter boundary. That containment must remain intact.

The harness should be updated so that during runtime composition it receives:

* primary model route
* primary tool bindings
* subagent asset bundles
* per-role resolved model routes
* per-role tool bindings
* global skills
* subagent-local skills

### 12.2 Introduce `subagent_compiler.py`

This helper should translate from project-owned structures into Deep Agent-native subagent definitions.

Input:

* `SubagentAssetBundle`
* `ResolvedModelRoute`
* resolved project tool bindings
* role-local skills

Output:

* whatever Deep Agent-native object or config structure is required by the adapter

This keeps conversion logic out of the harness and reduces framework bleed.

### 12.3 Compilation rules

For each role:

* `name` comes from role assets
* `description` comes from the manifest
* `system_prompt` is assembled from role identity + system prompt overlay
* `model` comes from `ModelResolver`
* `tools` come only from `RoleToolScopeResolver`
* `skills` come from the role-local skill loader

### 12.4 Avoid custom orchestration

Do not add runtime code that explicitly sequences planner → coder → verifier. Deep Agent should decide when to invoke subagents through its native mechanism. The runtime’s role is to provide the governed subagent definitions and observe execution. This is the core design correction for Milestone-3.

---

## 13. Prompt Assembly Rules

### 13.1 Primary agent

The existing primary prompt construction should remain, with identity and policy injected as before.

### 13.2 Subagents

Each subagent should receive a role-specific prompt assembled from:

* project/global identity constraints that must apply to all agents
* role-local `IDENTITY.md`, if present
* role-local `SYSTEM_PROMPT.md`, if present
* tool and scope framing generated by the runtime

Recommended order:

```text
1. global runtime safety/policy framing
2. inherited identity/doctrine that applies to all roles
3. role identity
4. role system prompt overlay
5. tool/scope summary
```

This gives specialization without losing consistency.

---

## 14. Eventing and Observability

The protocol spec already reserves `subagent.started` and `subagent.completed`, and the architecture explicitly calls for sub-agent invocation traces.

### 14.1 Implement real `subagent.completed`

Add the missing event type to:

* protocol models
* runtime event envelope factories
* CLI rendering logic, if needed

### 14.2 Upgrade `subagent.started`

Today it is effectively a placeholder. Replace the synthetic single-role behavior with real role data derived from the executing Deep Agent subagent.

Suggested payload for `subagent.started`:

* `role`
* `name`
* `model_profile`
* `objective`

Suggested payload for `subagent.completed`:

* `role`
* `name`
* `summary`
* `outcome`

### 14.3 Adapter-side stream projection

If Deep Agent exposes subgraph/subagent activity through streaming, translate that activity into runtime event envelopes inside the adapter or an adapter-adjacent translator.

The runtime event model must stay project-owned even if the source is a Deep Agent stream.

### 14.4 Task snapshot updates

If `TaskSnapshot.active_subagent` already exists, update it using the real executing role rather than the current placeholder behavior.

---

## 15. Bootstrap and Runtime Composition Changes

### 15.1 Composition root updates

Runtime bootstrap should now compose:

* `FileSystemSubagentRegistry`
* `ModelResolver`
* `RoleToolScopeResolver`
* minimal `SkillRegistry` / loader
* updated `LangChainDeepAgentHarness`

### 15.2 Config inspection

Since model routing is becoming real, expose resolved routing in diagnostics or config inspection where practical. The current status specifically notes that routing is not yet inspectable.

A minimal version is enough:

* primary resolved model
* resolved model per role
* origin of resolution

---

## 16. Suggested Role Baselines

Start with the five roles already present in the architecture and ADRs.

### Planner

Purpose: decomposition and plan maintenance
Suggested tool scope:

* `read_files`
* `memory_lookup`
* `plan_update`

### Researcher

Purpose: repo/documentation discovery and synthesis
Suggested tool scope:

* `read_files`
* `memory_lookup`
* `artifact_inspect`

### Coder

Purpose: implementation work
Suggested tool scope:

* `read_files`
* `write_files`
* `execute_commands`

### Verifier

Purpose: validation and checks
Suggested tool scope:

* `read_files`
* `execute_commands`
* `artifact_inspect`

### Librarian

Purpose: memory support and durable knowledge curation
Suggested tool scope:

* `memory_lookup`
* `memory_promote`
* `read_files`

Keep these conservative at first. The goal is not exhaustive capability; it is governed specialization.

---

## 17. Test Plan

Milestone-3 needs strong automated validation because it introduces a new axis of runtime behavior.

### 17.1 Unit tests

Add unit tests for:

* manifest parsing and validation
* duplicate role detection
* missing asset handling
* model resolution precedence
* role tool scope resolution
* prompt assembly
* skill discovery and validation
* event payload construction

### 17.2 Adapter tests

Add focused adapter tests for:

* compilation of one project-owned role into one Deep Agent-native subagent
* compilation of multiple roles
* role-specific model attachment
* role-specific tools only
* role-specific skills only

### 17.3 Runtime integration tests

Add integration tests for:

* bootstrap succeeds with valid `agents/subagents/*`
* runtime creates a Deep Agent harness with multiple compiled subagents
* task execution emits `subagent.started`
* task execution emits `subagent.completed`
* `TaskSnapshot.active_subagent` reflects the real active role
* subagent model overrides from config are honored

### 17.4 Regression tests

Protect the existing Milestone-2 surface:

* primary single-agent flows still work if subagent assets are incomplete or temporarily absent, if that fallback is allowed by design
* approvals still work on coder/verifier actions
* sandbox boundaries remain enforced
* artifact registration still attributes source role where available

---

## 18. Recommended Implementation Order

Use this exact implementation order.

### Step 1

Create `agents/subagents/*` directories and manifests.

### Step 2

Introduce `SubagentDefinition`, `SubagentAssetBundle`, and `SubagentRegistry`.

### Step 3

Implement filesystem-backed registry and validation.

### Step 4

Implement `ModelResolver` and tests.

### Step 5

Implement `RoleToolScopeResolver` and tests.

### Step 6

Implement minimal role-local skill discovery.

### Step 7

Add `subagent_compiler.py`.

### Step 8

Update `LangChainDeepAgentHarness` to pass compiled subagents into Deep Agent creation.

### Step 9

Project Deep Agent subagent activity into runtime events.

### Step 10

Update task snapshots, diagnostics, and integration tests.

This sequence keeps the project-owned model stable before touching the framework adapter.

---

## 19. Risks and Mitigations

### Risk: framework leakage into the runtime

Mitigation: keep all Deep Agent-native objects inside `services/deepagent_runtime/...`; use only project-owned dataclasses and ports elsewhere. This is a core architecture rule.

### Risk: capability bleed across roles

Mitigation: bind tools per role through `RoleToolScopeResolver`; do not share a flat tool pool. This directly addresses an identified architectural risk.

### Risk: brittle role prompts

Mitigation: use a simple prompt assembly model first; avoid overengineering role prompt composition in this milestone.

### Risk: incomplete Deep Agent stream observability

Mitigation: project the best available subagent lifecycle signals now; keep event translation isolated so it can be refined without changing runtime contracts.

### Risk: skill subsystem expansion

Mitigation: do only discovery/loading for role attachment; defer richer skill management.

---

## 20. QA Checklist

Milestone-3 should not be considered complete until all of the following are true.

### Architecture

* LangChain/Deep Agent types remain confined to the adapter layer.
* The runtime owns subagent definitions, routing, and policy.
* The CLI remains unchanged as a thin client.

### Registry and assets

* `agents/subagents/planner|researcher|coder|verifier|librarian` exist.
* Each role has a valid manifest.
* Registry loading fails clearly on invalid assets.

### Model routing

* `models.subagents.*` config is actually used at runtime.
* Resolved routing can be inspected in diagnostics or tests.
* Fallback behavior is deterministic.

### Tool scopes

* Each role gets only its allowed tools.
* Policy and approval controls still apply to those tools.

### Skills

* Role-local skills are discovered from the expected path.
* Invalid skill assets fail fast or are surfaced clearly.

### Adapter behavior

* Deep Agent is created with multiple native subagents.
* No runtime-owned planner/coder/verifier scheduler exists outside the adapter.
* Role definitions are compiled inside the adapter boundary.

### Observability

* `subagent.started` is emitted with real role data.
* `subagent.completed` is emitted.
* `TaskSnapshot.active_subagent` reflects real execution.

### Stability

* Existing Milestone-2 behaviors continue to pass.
* Sandbox boundaries still hold.
* Approval-driven pause/resume still works.

---

## 21. Definition of Done

Milestone-3 is done when the codebase demonstrates a **real, governed, Deep Agent-native subagent system** with:

* project-owned subagent role assets
* runtime-owned registry, routing, and tool scoping
* adapter compilation into Deep Agent-native subagents
* role-specific model use
* role-specific skill attachment
* runtime-visible subagent lifecycle events

At that point, the project will have closed the major gap identified in `docs/current.status.md`: it will no longer be just a durable single-agent runtime with placeholder subagent vocabulary, but a real multi-role harness aligned with the master spec and ADR-0006.
