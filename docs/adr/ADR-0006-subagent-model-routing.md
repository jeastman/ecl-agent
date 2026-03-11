# ADR-0006 — Sub-Agent and Model Routing Strategy

## Status
Accepted

## Date
2026-03-10

## Context

The runtime will use a primary DeepAgent with a set of sub-agents to support long-running, autonomous work. Different roles may benefit from different model configurations, tool scopes, and behavioral constraints.

A single flat agent with unrestricted tools is likely to be less stable, less explainable, and harder to govern than a role-oriented sub-agent system.

## Decision

We will implement a role-based sub-agent registry with explicit model routing.

Initial conceptual roles:
- **Planner** — decomposes work and maintains milestone structure
- **Researcher** — gathers and synthesizes relevant information
- **Coder** — writes and modifies implementation artifacts
- **Verifier** — evaluates outputs against criteria and runs checks
- **Librarian** — manages retrieval and memory-oriented support

Each role will define:
- purpose
- allowed tools
- visible filesystem scope
- model selection policy
- output expectations

Model configuration will be first-class in application config rather than a single global model setting.

## Rationale

This provides:
- clearer responsibility boundaries
- better governance
- easier tuning of model cost vs. capability
- better alignment between task type and execution mode

It also supports future experimentation without destabilizing the whole runtime.

## Consequences

### Positive
- More predictable autonomous behavior
- Sharper tool and file scope boundaries
- Easier model tuning and cost control
- Better observability of role behavior

### Negative
- Requires routing and orchestration logic
- Adds configuration complexity
- Over-specialization could create coordination overhead if poorly designed

## Alternatives Considered

### Single agent with tool selection only
Rejected because it hides responsibility boundaries and makes behavior harder to reason about.

### Static model for all roles
Rejected because model needs are not identical across planning, coding, verification, and research tasks.

## Config Shape

Illustrative configuration:

```toml
[models.default]
provider = "openai"
model = "gpt-5"

[models.primary_agent]
provider = "anthropic"
model = "claude-sonnet-4-5"

[models.subagents.planner]
provider = "anthropic"
model = "claude-sonnet-4-5"

[models.subagents.researcher]
provider = "openai"
model = "gpt-5-mini"

[models.subagents.coder]
provider = "openai"
model = "gpt-5"

[models.subagents.verifier]
provider = "anthropic"
model = "claude-sonnet-4-5"
```

## Policy Notes

- Sub-agents are explicit architectural roles, not ad hoc prompt fragments
- The runtime owns model resolution
- Clients do not choose sub-agent internals directly
- Tool scopes should be defined per role
- Verification should remain distinct from code generation where feasible

## Follow-up Work
- Define sub-agent registry schema
- Define routing rules from task phase to sub-agent role
- Define role-specific prompts, policies, and tool scopes
- Add observability around role invocation and output quality
