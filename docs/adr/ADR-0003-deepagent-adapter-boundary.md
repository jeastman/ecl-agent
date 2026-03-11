# ADR-0003 — DeepAgent Adapter Boundary

## Status
Accepted

## Date
2026-03-10

## Context

The runtime will use a LangChain DeepAgent implemented in Python. DeepAgent provides valuable capabilities, but the project mandate requires strong architecture, longevity, and a domain-centered design.

If library-specific types and semantics leak throughout the codebase, the system will become dependent on framework internals. That would make upgrades harder, increase coupling, and weaken the project’s own ubiquitous language.

## Decision

We will wrap LangChain DeepAgent behind an internal adapter boundary.

The runtime core will depend on project-defined interfaces such as:
- `AgentHarness`
- `TaskRunner`
- `ModelResolver`
- `SubAgentRegistry`
- `MemoryStore`
- `ExecutionSandbox`
- `ArtifactStore`
- `PolicyEngine`

A LangChain-specific adapter will implement those interfaces.

## Rationale

This keeps the system centered on its own domain concepts:
- task
- run
- identity
- policy
- memory
- artifact
- approval
- sub-agent role

rather than external framework terminology.

This also preserves the ability to:
- replace or augment DeepAgent later
- test the runtime with fakes and mocks
- isolate framework-specific upgrade risk
- apply Triadic Lens discipline consistently

## Consequences

### Positive
- Stable internal abstractions
- Framework upgrades are localized
- Better unit and integration testability
- Clear dependency inversion
- Cleaner monorepo boundaries

### Negative
- Requires adapter design work
- Some framework capabilities may need explicit mapping
- Slightly more code than using DeepAgent directly everywhere

## Alternatives Considered

### Use DeepAgent types directly throughout the runtime
Rejected because it creates framework lock-in and weakens architecture.

### Hide DeepAgent only at the top-level composition root
Rejected because leakage would still occur in task, memory, and sub-agent orchestration code.

## Boundary Rule

Only the LangChain adapter layer may:
- construct DeepAgent instances
- work directly with DeepAgent-specific middleware types
- translate framework messages into runtime domain events
- map runtime model routing into framework model config
- bind tools, backends, and skills to framework constructs

The domain and application layers may not depend on LangChain-specific classes.

## Follow-up Work
- Define runtime ports in a language-neutral architecture doc
- Create the Python adapter package
- Add mapping tests between runtime events and framework callbacks
