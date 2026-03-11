# Architecture Notes

- `runtime.example.toml` is the runtime configuration example and includes the Milestone 2 persistence section.
- Milestone 2 Phase 1 adds runtime-owned SQLite-backed seams for checkpoint metadata, thread bindings, approval records, memory records, persisted events, diagnostics, and run metrics.
- Milestone 2 Phase 2 adds checkpoint-backed pause/resume plumbing, `task.resume`, restart-time recovery scanning, and a DeepAgent-side checkpoint adapter that keeps LangGraph checkpoint payloads behind the service boundary.
- Milestone 2 Phase 3 adds runtime-owned memory promotion rules, seeded identity-memory inspection, and `memory.inspect`, while keeping checkpoint state separate from durable memory records.
- Future architecture notes can live here without mixing with ADRs or milestone plans.
