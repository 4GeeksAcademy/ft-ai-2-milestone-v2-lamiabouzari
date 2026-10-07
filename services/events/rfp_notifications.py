"""Publish one rfp_ticket_created frame from persisted intake metadata."""

from __future__ import annotations

from typing import Any

from data.pipelines.rfp_intake.store import get_ticket, ticket_snapshot
from events.bus import bus
from events.frames import EVENT_NAME


def persisted_rfp_id(ticket: Any, snapshot: dict[str, Any] | None) -> str | None:
    """Read rfp_tickets.rfp_id. Never substitute the ticket primary key."""
    raw = getattr(ticket, "rfp_id", None)
    if raw:
        return str(raw)
    if snapshot and snapshot.get("rfp_id"):
        return str(snapshot["rfp_id"])
    return None


def maybe_publish_rfp_created(ticket_id: str) -> dict[str, Any] | None:
    """Publish only after a valid RFP's client fields are stored and status is analyzing."""
    ticket = get_ticket(ticket_id)
    if ticket is None or ticket.status != "analyzing":
        return None
    snapshot = ticket_snapshot(ticket_id)
    metadata = (snapshot or {}).get("metadata") or {}
    client_name = str(metadata.get("client_name") or "").strip()
    client_country = str(metadata.get("client_country") or "").strip()
    services = [str(item) for item in (metadata.get("services_requested") or []) if str(item).strip()]
    if not client_name or not client_country or not services:
        return None
    payload = {
        "ticket_id": ticket.id,
        "rfp_id": persisted_rfp_id(ticket, snapshot),
        "client_name": client_name,
        "client_country": client_country,
        "services_requested": services,
        "status": "analyzing",
        "created_at": ticket.created_at.isoformat(),
    }
    if not bus.publish_once(ticket.id, EVENT_NAME, payload):
        return None
    return payload
