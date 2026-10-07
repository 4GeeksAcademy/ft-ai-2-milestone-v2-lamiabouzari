"""SSE wire format for rfp_ticket_created. Never a generic message event."""

from __future__ import annotations

import json
from typing import Any

EVENT_NAME = "rfp_ticket_created"
KEEPALIVE_SECONDS = 15.0

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def format_frame(event_id: str, event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event_id}\nevent: {event}\ndata: {payload}\n\n"


def keepalive_frame() -> str:
    return ": keepalive\n\n"
