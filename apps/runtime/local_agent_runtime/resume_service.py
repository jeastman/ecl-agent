from __future__ import annotations

from dataclasses import dataclass

from apps.runtime.local_agent_runtime.task_runner import TaskRunner
from packages.protocol.local_agent_protocol.models import TaskSnapshot


@dataclass(slots=True)
class ResumeService:
    task_runner: TaskRunner
    identity_bundle_text: str

    def resume(self, task_id: str, run_id: str | None = None) -> TaskSnapshot:
        return self.task_runner.resume_run(
            task_id,
            run_id,
            identity_bundle_text=self.identity_bundle_text,
        )
