"""Structured logging for MCP tool invocations.

Every tool call is logged with at least: tool name, authenticated subject
(when available), outcome, and a UTC timestamp. Access tokens and other
secrets are never logged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

logger = logging.getLogger("mcps.tools")

if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _subject_for_log(subject: str | None) -> str:
    return subject or "anonymous"


@contextmanager
def log_tool_invocation(tool_name: str, subject: str | None) -> Iterator[None]:
    """Log a single MCP tool invocation with its outcome.

    Logs on both success and failure; re-raises any exception unchanged.
    """
    started = time.monotonic()
    timestamp = datetime.now(UTC).isoformat()
    try:
        yield
    except Exception as exc:
        duration_ms = round((time.monotonic() - started) * 1000, 2)
        logger.info(
            "tool=%s subject=%s outcome=error error_type=%s timestamp=%s duration_ms=%s",
            tool_name,
            _subject_for_log(subject),
            type(exc).__name__,
            timestamp,
            duration_ms,
        )
        raise
    else:
        duration_ms = round((time.monotonic() - started) * 1000, 2)
        logger.info(
            "tool=%s subject=%s outcome=success timestamp=%s duration_ms=%s",
            tool_name,
            _subject_for_log(subject),
            timestamp,
            duration_ms,
        )
