# CLI App

The CLI owns command parsing, runtime process control, request rendering, and error presentation. It does not own task orchestration logic.

Current command surface:

- `agent health`
- `agent run "<objective>"`
- `agent status <task_id> [--run-id <run_id>]`
- `agent logs <task_id> [--run-id <run_id>]`
- `agent artifacts <task_id> [--run-id <run_id>]`
- `agent approvals <task_id> [--run-id <run_id>]`
- `agent diagnostics <task_id> [--run-id <run_id>]`
- `agent approve <approval_id> --decision approve|reject [--task-id <task_id>] [--run-id <run_id>]`
- `agent resume <task_id> [--run-id <run_id>]`
- `agent memory [--task-id <task_id>] [--run-id <run_id>] [--scope <scope>] [--namespace <namespace>]`
- `agent config`

The CLI remains a thin client over JSON-RPC stdio:

- `run` submits work through `task.create`
- `status` reads runtime-owned task state through `task.get`
- `logs` replays runtime events through `task.logs.stream`
- `artifacts` lists runtime-owned artifact metadata through `task.artifacts.list`
- `approvals` reads runtime-owned approval state through `task.approvals.list`
- `diagnostics` reads persisted runtime diagnostics through `task.diagnostics.list`
- `approve` submits approval decisions through `task.approve`
- `resume` resumes runtime-owned checkpoint-backed runs through `task.resume`
- `memory` inspects runtime-owned memory state through `memory.inspect`
- `config` inspects runtime-owned redacted config through `config.get`

The CLI does not:

- decide policy outcomes
- redact secrets client-side
- reconstruct approval, checkpoint, or recovery state locally
