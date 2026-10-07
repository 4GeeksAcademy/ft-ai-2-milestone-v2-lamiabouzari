"""Process-local rate limit for POST /agent/query.

Hits live in this process only. A multi-worker deployment should replace
this with a shared store such as Redis. The check runs before the support
agent, so a rejected call does not start model execution.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from config import settings

_HITS: dict[str, list[float]] = defaultdict(list)
_LOCK = Lock()


def reset_agent_rate_limit() -> None:
    """Drop recorded hits. Tests call this so cases do not depend on order."""
    with _LOCK:
        _HITS.clear()


def allow_agent_request(subject: str, *, now: float | None = None) -> bool:
    """Return True when the subject is still inside the configured window."""
    limit = settings.agent_rate_limit_requests
    window = settings.agent_rate_limit_window_seconds
    if limit < 1 or window < 1:
        return False
    moment = time.monotonic() if now is None else now
    key = subject.strip() or "anonymous"
    with _LOCK:
        recent = [stamp for stamp in _HITS[key] if moment - stamp < window]
        if len(recent) >= limit:
            _HITS[key] = recent
            return False
        recent.append(moment)
        _HITS[key] = recent
        return True
