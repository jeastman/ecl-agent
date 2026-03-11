from __future__ import annotations

import uuid


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def new_task_id() -> str:
    return _new_id("task")


def new_run_id() -> str:
    return _new_id("run")


def new_event_id() -> str:
    return _new_id("evt")


def new_artifact_id() -> str:
    return _new_id("artifact")


def new_correlation_id() -> str:
    return _new_id("corr")
