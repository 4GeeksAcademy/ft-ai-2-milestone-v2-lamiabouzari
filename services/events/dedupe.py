"""Ticket list merge used by refetch-then-SSE recovery.

The backoffice helper in uis/backoffice/src/lib/rfp-events.ts follows these rules:
merge and apply key only on ticket_id, and a later SSE frame does not add a second row.
"""

from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T", bound=dict[str, Any])


def next_backoff_ms(attempt: number) -> int:
    """1s, 2s, 4s, 8s, … capped at 30s. attempt 0 is the first retry."""
    return min(1000 * (2**attempt), 30_000)


def merge_recovered(current: list[T], incoming: list[T]) -> dict[str, Any]:
    """Server rows replace the same ticket_id. Local-only rows stay. New ids are added once."""
    known = {str(ticket["ticket_id"]) for ticket in current}
    incoming_ids = {str(ticket["ticket_id"]) for ticket in incoming}
    local_only = [ticket for ticket in current if str(ticket["ticket_id"]) not in incoming_ids]
    added = [ticket for ticket in incoming if str(ticket["ticket_id"]) not in known]
    return {"tickets": [*incoming, *local_only], "added": added}


def apply_created(current: list[T], event: dict[str, Any], created: T) -> dict[str, Any]:
    """Insert a new ticket or keep the existing row. Never append a second copy."""
    ticket_id = str(event["ticket_id"])
    for ticket in current:
        if str(ticket["ticket_id"]) == ticket_id:
            return {"tickets": list(current), "added": False}
    return {"tickets": [created, *current], "added": True}
