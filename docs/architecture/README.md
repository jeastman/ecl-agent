# Architecture Notes

- `runtime.example.toml` is the runtime configuration example and includes the Milestone 2 persistence section.
- Milestone 2 Phase 1 adds runtime-owned SQLite-backed seams for checkpoint metadata, thread bindings, approval records, memory records, persisted events, diagnostics, and run metrics.
- Milestone 2 Phase 2 adds checkpoint-backed pause/resume plumbing, `task.resume`, restart-time recovery scanning, and a DeepAgent-side checkpoint adapter that keeps LangGraph checkpoint payloads behind the service boundary.
- Milestone 2 Phase 3 adds runtime-owned memory promotion rules, seeded identity-memory inspection, and `memory.inspect`, while keeping checkpoint state separate from durable memory records.
- Milestone 2 Phase 5 adds thin-client inspection surfaces for approvals, diagnostics, memory, resume, and redacted config, with runtime-owned handlers for `task.approvals.list`, `task.diagnostics.list`, `task.resume`, `memory.inspect`, and `config.get`.
- Phase 5 also treats persisted event history and diagnostics as restart-safe inspection data rather than transient stream-only telemetry.
- Milestone 2 Phase 6 closes the milestone by validating restart recovery, approval recovery, runtime/client separation, and documentation consistency against the implemented behavior.
- Future architecture notes can live here without mixing with ADRs or milestone plans.
