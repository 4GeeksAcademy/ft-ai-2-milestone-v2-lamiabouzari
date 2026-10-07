"""SQLModel checkpointer. Checkpoints live in the same database as the ticket.

This pause is a durable row, not LangGraph ``interrupt()``. The service already
stores tickets in SQLModel, so each department thread is one
``rfp_approval_checkpoints`` row keyed by ``rfp-{ticket_id}:{department_id}``.

That matches an interrupt/resume pair: ``start_approval`` writes
``node=approval_interrupt`` and ``interrupted=True`` before a department can
be approved; ``resume_approval`` loads that row and continues only while the
flag is set. Approve does not re-enter Part 1 or Part 2. Reject and
request_changes re-enter only that department's Part 2 loop. Another
department's row is not read or written.
"""

from __future__ import annotations

import copy
import threading
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from data.pipelines.rfp_intake.store import get_engine
from models.rfp import RfpApprovalCheckpoint, RfpDepartmentSection, RfpTicket

_LOCK = threading.Lock()


def _session() -> Session:
    return Session(get_engine(), expire_on_commit=False)


def save_checkpoint(state: dict[str, Any]) -> dict[str, Any]:
    """Upsert one department interrupt. The draft stored here is not rewritten."""
    payload = copy.deepcopy(state)
    thread_id = str(payload["thread_id"])
    with _LOCK:
        with _session() as session:
            row = session.exec(
                select(RfpApprovalCheckpoint).where(RfpApprovalCheckpoint.thread_id == thread_id)
            ).first()
            if row is None:
                row = RfpApprovalCheckpoint(
                    ticket_id=str(payload["ticket_id"]),
                    department_key=str(payload["department_id"]),
                    thread_id=thread_id,
                )
            row.ticket_id = str(payload["ticket_id"])
            row.department_key = str(payload["department_id"])
            row.node = str(payload.get("node") or "approval_interrupt")
            row.interrupted = bool(payload.get("interrupted", True))
            row.revision_count = int(payload.get("revision_count") or 0)
            row.state = payload
            row.updated_at = datetime.now(UTC)
            session.add(row)
            session.commit()
    return payload


def load_checkpoint(thread_id: str) -> dict[str, Any] | None:
    with _session() as session:
        row = session.exec(
            select(RfpApprovalCheckpoint).where(RfpApprovalCheckpoint.thread_id == thread_id)
        ).first()
        if row is None:
            return None
        state = copy.deepcopy(row.state or {})
        state["thread_id"] = row.thread_id
        state["node"] = row.node
        state["interrupted"] = row.interrupted
        state["revision_count"] = row.revision_count
        state["department_id"] = row.department_key
        state["ticket_id"] = row.ticket_id
        return state


def set_section_approval(
    ticket_id: str,
    department_id: str,
    approval_status: str,
) -> None:
    """Update approval status only. The Part 2 draft stays in place."""
    with _LOCK:
        with _session() as session:
            row = session.exec(
                select(RfpDepartmentSection).where(
                    RfpDepartmentSection.ticket_id == ticket_id,
                    RfpDepartmentSection.department_key == department_id,
                )
            ).first()
            if row is None:
                raise KeyError(department_id)
            row.approval_status = approval_status
            session.add(row)
            session.commit()


def set_ticket_fields(ticket_id: str, **fields: Any) -> None:
    with _LOCK:
        with _session() as session:
            ticket = session.get(RfpTicket, ticket_id)
            if ticket is None:
                raise KeyError(ticket_id)
            for key, value in fields.items():
                setattr(ticket, key, value)
            ticket.updated_at = datetime.now(UTC)
            session.add(ticket)
            session.commit()
