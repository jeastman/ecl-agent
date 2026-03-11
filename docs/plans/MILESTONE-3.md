# MILESTONE-3.md

Deep Agent Sub-Agent Integration

---

# 1. Overview

Milestone-3 introduces **native sub-agent capabilities** to the Local Agent Harness by integrating with **LangChain Deep Agent's built-in subagent system**.

The runtime will define and govern **role-based agent definitions**, which are compiled into **Deep Agent subagents** by the adapter layer.

The Deep Agent framework will remain responsible for:

* subagent delegation
* task routing
* context management
* multi-agent coordination

The Local Agent Harness runtime will remain responsible for:

* defining agent roles
* model routing
* tool scoping
* skill attachment
* sandbox and filesystem policy enforcement
* runtime observability
* configuration

This milestone transforms the system from a **single-agent runtime** into a **structured multi-agent environment**, while maintaining strict adherence to the architectural rule that **LangChain remains inside the adapter boundary**.

---

# 2. Goals

Milestone-3 must enable the following capabilities.

## 2.1 Role-Based Agents

The system must support **multiple agent roles**, each with:

* identity
* prompt overlays
* model routing
* tool scopes
* skill sets

Example roles:

* planner
* researcher
* coder
* verifier
* librarian

These roles are **runtime concepts**, not Deep Agent concepts.

---

## 2.2 Native Deep Agent Subagents

Role definitions must be compiled into **Deep Agent subagents**.

The system **must not implement its own orchestration engine**.

Instead:

```
Runtime Role Definition
        ↓
Adapter Compilation
        ↓
Deep Agent Subagent
        ↓
Deep Agent Delegation
```

Deep Agent will handle:

* subagent invocation
* tool-like routing
* context management
* execution sequencing

---

## 2.3 Model Routing

Each role may use a different model.

The runtime configuration already supports this:

```
[models.primary]

[models.subagents.planner]

[models.subagents.researcher]

[models.subagents.coder]

[models.subagents.verifier]
```

The runtime must resolve the correct model per role.

---

## 2.4 Tool Scope Governance

Each role must have a **restricted set of tools**.

This provides:

* safety
* explainability
* specialization
* cost control

Example:

Planner tools:

```
read_files
memory_lookup
plan_update
```

Coder tools:

```
read_files
write_files
execute_commands
```

Verifier tools:

```
execute_commands
read_files
artifact_inspect
```

---

## 2.5 Skill Attachment

Skills must be attachable to:

* the primary agent
* specific subagents

This aligns with the `agentskills.io` specification already adopted by the project.

Skills may include:

* python UV scripts
* domain prompts
* structured workflows

---

## 2.6 Observability

The runtime must expose subagent lifecycle events.

New events:

```
subagent.started
subagent.completed
```

These events allow the CLI and future UI clients to display multi-agent execution.

---

# 3. Architecture Alignment

Milestone-3 must adhere to the existing architecture rules.

---

## 3.1 Runtime Owns Agent Definitions

Agent roles are defined by the runtime.

Example directory:

```
agents/

  primary-agent/

  subagents/
      planner/
      researcher/
      coder/
      verifier/
      librarian/
```

Each role may contain:

```
IDENTITY.md
SYSTEM_PROMPT.md
skills/
```

---

## 3.2 Adapter Compiles to Deep Agent

The `LangChainDeepAgentHarness` adapter must convert runtime roles into Deep Agent subagents.

Conceptually:

```
Runtime Role Definition
        ↓
LangChain Adapter
        ↓
Deep Agent Subagent Configuration
```

The adapter is the **only place that interacts with LangChain APIs**.

This preserves Clean Architecture boundaries.

---

## 3.3 Runtime Remains Framework-Independent

The runtime must **never depend on LangChain types**.

All LangChain integration must remain inside the adapter layer.

---

# 4. Subagent Definition Model

The runtime introduces a new domain model.

## 4.1 SubagentDefinition

A subagent definition describes a role.

Fields:

```
id
name
description
model_profile
system_prompt_overlay
tool_scope
skill_paths
memory_scope
filesystem_scope
```

Example:

```
planner

description: strategic task planner

model_profile: planner

tool_scope:
  - read_files
  - memory_lookup
  - plan_update
```

---

## 4.2 Subagent Registry

The runtime must include a registry responsible for:

```
register_subagent()
get_subagent(id)
list_subagents()
```

The registry loads definitions from the filesystem.

---

# 5. Model Resolution

The runtime must implement a `ModelResolver`.

Resolution order:

```
1 project override
2 subagent model profile
3 primary agent model
4 default model
```

This logic already aligns with the ADR on subagent model routing.

---

# 6. Tool Binding

The runtime must enforce tool scopes during adapter construction.

Each subagent receives **only the tools in its scope**.

Example:

```
planner → planning tools

researcher → retrieval tools

coder → filesystem + execution tools

verifier → execution + inspection tools
```

---

# 7. Skills Integration

Skills must be loadable from the filesystem.

Directory structure:

```
agents/subagents/<role>/skills/
```

Skills are passed to the Deep Agent adapter when constructing subagents.

---

# 8. Adapter Responsibilities

The `LangChainDeepAgentHarness` must now support:

```
create_deep_agent(
  model=primary_model,
  tools=primary_tools,
  subagents=subagent_definitions,
  skills=global_skills
)
```

Each runtime role becomes a Deep Agent subagent.

The adapter must map:

```
runtime role
    ↓
deep agent subagent
```

Fields mapped:

```
role.name → subagent.name
role.description → subagent.description
role.system_prompt → subagent.system_prompt
role.model → subagent.model
role.tools → subagent.tools
role.skills → subagent.skills
```

---

# 9. Runtime Events

Two new runtime events must be added.

---

## 9.1 subagent.started

Emitted when a subagent begins execution.

Payload:

```
runId
subagentId
taskDescription
timestamp
```

---

## 9.2 subagent.completed

Emitted when execution completes.

Payload:

```
runId
subagentId
status
duration
timestamp
```

---

# 10. Filesystem Layout

The repository must include the following structure.

```
agents/

  primary-agent/

  subagents/

      planner/
          IDENTITY.md
          SYSTEM_PROMPT.md
          skills/

      researcher/

      coder/

      verifier/

      librarian/
```

---

# 11. Configuration

Runtime configuration must support subagent models.

Example:

```
[models.primary]
provider = "openai"
model = "gpt-4.1"

[models.subagents.planner]
model = "gpt-4.1"

[models.subagents.researcher]
model = "gpt-4.1-mini"

[models.subagents.coder]
model = "gpt-4.1"

[models.subagents.verifier]
model = "gpt-4.1-mini"
```

---

# 12. Acceptance Criteria

Milestone-3 is complete when:

### Subagent Definitions

* runtime can load subagent definitions
* definitions support prompts, tools, models, and skills

---

### Adapter Integration

* adapter compiles roles into Deep Agent subagents
* Deep Agent executes with multiple subagents

---

### Tool Scoping

* each subagent receives only allowed tools

---

### Model Routing

* subagent models resolve correctly from configuration

---

### Skills

* role-specific skills load successfully

---

### Events

* `subagent.started` emitted
* `subagent.completed` emitted

---

### CLI Compatibility

The CLI must work exactly as before.

No CLI changes are required for Milestone-3.

---

# 13. Out of Scope

Milestone-3 intentionally excludes:

* skill authoring UX
* skill generation
* advanced orchestration policies
* web UI
* visual subagent dashboards
* automatic role discovery
* distributed agent execution

These capabilities will be addressed in later milestones.

---

# 14. Expected Outcome

After Milestone-3 the system will support:

```
User Task
     ↓
Primary Agent
     ↓
Deep Agent Delegation
     ↓
Planner
Researcher
Coder
Verifier
Librarian
     ↓
Sandbox + Memory + Artifacts
     ↓
Runtime Events
```

The Local Agent Harness will now function as a **governed multi-agent runtime** built on Deep Agent.

---

# 15. Phased Delivery Plan

Milestone 3 should be executed in phases so the runtime gains governed subagent behavior incrementally, with architecture seams validated before Deep Agent compilation and end-to-end verification.

Phase documents:

- [Phase 1 — Subagent Assets and Registry Foundations](/Users/jeastman/Projects/e/ecl-agent/docs/plans/milestone-3.phase-1.md)
- [Phase 2 — Routing, Tool Governance, and Skill Discovery](/Users/jeastman/Projects/e/ecl-agent/docs/plans/milestone-3.phase-2.md)
- [Phase 3 — Deep Agent Compilation and Runtime Wiring](/Users/jeastman/Projects/e/ecl-agent/docs/plans/milestone-3.phase-3.md)
- [Phase 4 — Eventing, Verification, and Documentation Closure](/Users/jeastman/Projects/e/ecl-agent/docs/plans/milestone-3.phase-4.md)
