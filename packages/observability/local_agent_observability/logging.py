from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any

from packages.protocol.local_agent_protocol.models import EventEnvelope


def _ts() -> str:
    return datetime.now(UTC).isoformat()


def log_record(level: str, message: str, correlation_id: str | None, **fields: Any) -> None:
    payload = {
        "record_type": "log",
        "timestamp": _ts(),
        "level": level,
        "message": message,
        "correlation_id": correlation_id,
        **fields,
    }
    print(json.dumps(payload), file=sys.stderr, flush=True)


def emit_event(event: EventEnvelope) -> None:
    payload = {
        "record_type": "event",
        "timestamp": _ts(),
        "event": event.to_dict(),
    }
    print(json.dumps(payload), file=sys.stderr, flush=True)
