# ADR-0005 — Sandbox and Filesystem Policy

## Status
Accepted

## Date
2026-03-10

## Context

The agent must be able to inspect files, write artifacts, and execute commands. However, granting unconstrained host access would be unsafe and architecturally unsound. The project requires a tailored harness, not a raw shell with a language model attached.

The runtime therefore needs a controlled execution model for filesystem access and command execution.

## Decision

We will implement a governed execution sandbox with a rooted workspace and explicit zones:

1. **Workspace Zone**
   - Files that belong to the active task/project
   - Agent can read and write within policy constraints

2. **Scratch Zone**
   - Temporary execution output
   - Disposable, ephemeral artifacts
   - Safe place for transient generated files

3. **Memory Zone**
   - Durable runtime-managed memory artifacts
   - Not treated as a general-purpose project workspace

The agent will not receive unrestricted access to the host filesystem.

Command execution will occur through a sandboxed execution interface controlled by the runtime. The runtime will enforce:
- allowed working directories
- environment shaping
- execution policy
- artifact capture
- path normalization and isolation

## Rationale

The agent needs enough freedom to work, but the harness must preserve:
- safety
- predictability
- reproducibility
- explainability
- clean architecture boundaries

Filesystem and command access are capabilities granted by the application, not inherent rights of the agent.

## Consequences

### Positive
- Reduced risk of accidental host modification
- Clear artifact and workspace boundaries
- Better auditability of agent actions
- Easier future support for remote or containerized sandboxes

### Negative
- Some tasks may require explicit capability escalation
- More adapter work for command and filesystem access
- Requires careful design for path mapping and artifact promotion

## Alternatives Considered

### Full host filesystem access
Rejected due to safety and design concerns.

### Read-only workspace with out-of-band writes
Rejected because it undermines agent usefulness for implementation tasks.

### Container-first mandatory sandboxing
Deferred. It may be desirable later, but it is not required for the first local iteration if the rooted workspace policy is enforced cleanly.

## Policy Notes

- All agent-visible paths must be normalized through the sandbox layer
- Runtime-managed artifact export/import must remain separate from agent filesystem tools
- The CLI should not bypass sandbox policy to “help” the agent
- Approval policy may later gate high-impact execution operations

## Follow-up Work
- Define sandbox interface
- Define path mapping rules
- Define command execution result contract
- Define artifact capture and promotion rules
