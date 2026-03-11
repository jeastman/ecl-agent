# ADR-0004 — Memory Taxonomy and Persistence

## Status
Accepted

## Date
2026-03-10

## Context

The system requires memory, but “memory” is too broad to treat as one undifferentiated store. The agent will operate across long-running tasks, recurring project conventions, and guiding identity principles. These categories have different retention, retrieval, trust, and governance needs.

A single memory bucket would create ambiguity around what the agent is allowed to persist, retrieve, and treat as durable truth.

## Decision

We will implement a **memory taxonomy** with distinct categories:

1. **Run State Memory**
   - Working state for an active task or run
   - Checkpoints, summaries, intermediate notes
   - Scoped to a specific run or thread

2. **Project Memory**
   - Durable conventions, reusable knowledge, prior outcomes
   - Scoped to a workspace, repository, or project

3. **Identity and Policy Memory**
   - Loaded from controlled project artifacts such as `IDENTITY.md`
   - Considered governed input, not agent-authored freeform memory

4. **Ephemeral Scratch Memory**
   - Temporary notes, transient context, internal scratch artifacts
   - Not automatically promoted to durable memory

The initial implementation will support:
- run-local memory
- durable project memory through a store-backed persistence layer
- controlled identity ingestion from repository/project files

## Rationale

Different classes of memory imply different rules:
- persistence policy
- retrieval priority
- mutability
- reviewability
- provenance

This design allows the runtime to be explicit about what the agent knows and why it knows it.

## Consequences

### Positive
- Clear governance over persistence
- Better retrieval quality
- Reduced risk of memory pollution
- Supports explainability and auditability
- Aligns identity inputs with explicit project doctrine

### Negative
- More design effort than a single store
- Requires explicit classification logic
- Retrieval orchestration becomes more deliberate

## Alternatives Considered

### Single memory store with tags
Rejected as insufficiently explicit. Tags alone do not create strong enough boundaries or policies.

### No durable memory in initial release
Rejected because long-running autonomous work benefits materially from durable project knowledge.

## Policy Notes

- Agent-authored content is not automatically promoted to project memory
- Identity and policy material originate from controlled files and config
- Durable memory entries should capture provenance and scope
- Retrieval should prioritize identity/policy, then task-local state, then project memory as appropriate

## Follow-up Work
- Define memory record schema
- Define promotion rules from run state to project memory
- Define retrieval precedence and filtering rules
- Define user inspection and review mechanisms
