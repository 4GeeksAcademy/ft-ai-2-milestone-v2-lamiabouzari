"""Namespaced checkpoint identity. Tickets never share a thread."""

from __future__ import annotations


def make_thread_id(ticket_id: str, department_id: str) -> str:
    """Return ``rfp-{ticket_id}:{department_id}``."""
    if not ticket_id or not department_id:
        raise ValueError("thread_id requires a ticket id and a department id.")
    return f"rfp-{ticket_id}:{department_id}"
