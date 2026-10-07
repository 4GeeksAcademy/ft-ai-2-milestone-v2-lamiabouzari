"""Progressive reconnect delay shared with the backoffice chat client."""

from __future__ import annotations


def next_backoff_ms(attempt: int) -> int:
    """1s, 2s, 4s, 8s, ... capped at 30s."""
    return min(1000 * 2**attempt, 30_000)
