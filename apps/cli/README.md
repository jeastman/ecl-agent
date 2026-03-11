# CLI App

The CLI owns command parsing, runtime process control, request rendering, and error presentation. It does not own task orchestration logic.

Milestone 1 command surface:

- `agent health`
- `agent run "<objective>"`
- `agent status <task_id> [--run-id <run_id>]`
- `agent logs <task_id> [--run-id <run_id>]`
- `agent artifacts <task_id> [--run-id <run_id>]`

The CLI remains a thin client over JSON-RPC stdio:

- `run` submits work through `task.create`
- `status` reads runtime-owned task state through `task.get`
- `logs` replays runtime events through `task.logs.stream`
- `artifacts` lists runtime-owned artifact metadata through `task.artifacts.list`
