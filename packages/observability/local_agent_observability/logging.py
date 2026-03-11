from __future__ import annotations

import json
import sys
from typing import Any

from packages.protocol.local_agent_protocol.models import RuntimeEvent, utc_now_timestamp


def log_record(level: str, message: str, correlation_id: str | None, **fields: Any) -> None:
    payload = {
        "record_type": "log",
        "timestamp": utc_now_timestamp(),
        "level": level,
        "message": message,
        "correlation_id": correlation_id,
        **fields,
    }
    print(json.dumps(payload), file=sys.stderr, flush=True)


def emit_event(event: RuntimeEvent) -> None:
    print(json.dumps(event.to_dict()), file=sys.stderr, flush=True)
