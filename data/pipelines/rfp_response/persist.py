"""Persist Part 2 drafts on the existing RFP tables."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from data.pipelines.rfp_intake.store import get_engine
from models.rfp import RfpDepartmentSection, RfpTicket

_WRITE_LOCK = threading.Lock()

_STATUS_ORDER = ("intake_complete", "drafting", "under_evaluation", "needs_human_review")


def _session() -> Session:
    return Session(get_engine(), expire_on_commit=False)


def advance_status(ticket_id: str, status: str) -> None:
    """Move a ticket forward through Part 2. Never move it backward."""
    with _WRITE_LOCK:
        with _session() as session:
            ticket = session.get(RfpTicket, ticket_id)
            if ticket is None:
                raise KeyError(ticket_id)
            if ticket.status not in _STATUS_ORDER or status not in _STATUS_ORDER:
                return
            if _STATUS_ORDER.index(status) < _STATUS_ORDER.index(ticket.status):
                return
            ticket.status = status
            ticket.updated_at = datetime.now(UTC)
            session.add(ticket)
            session.commit()


def save_department_response(
    ticket_id: str,
    *,
    department_id: str,
    department_name: str,
    contact: str,
    key_aspects: list[str],
    open_questions: list[str],
    draft_content: str | None,
    evaluation_results: dict[str, Any] | None,
    iteration_count: int,
    section_status: str,
    approval_status: str | None,
    needs_human_review: bool,
) -> None:
    """Update one department row. Other departments on the ticket are left in place."""
    with _WRITE_LOCK:
        with _session() as session:
            row = session.exec(
                select(RfpDepartmentSection).where(
                    RfpDepartmentSection.ticket_id == ticket_id,
                    RfpDepartmentSection.department_key == department_id,
                )
            ).first()
            if row is None:
                row = RfpDepartmentSection(
                    ticket_id=ticket_id,
                    department_key=department_id,
                    department_name=department_name,
                    contact=contact,
                    key_aspects=list(key_aspects),
                    open_questions=list(open_questions),
                    extract_text="",
                )
            if draft_content is not None:
                row.draft_content = draft_content
            if evaluation_results is not None:
                row.evaluation_results = evaluation_results
            row.iteration_count = iteration_count
            row.section_status = section_status
            if approval_status is not None:
                row.approval_status = approval_status
            row.needs_human_review = needs_human_review
            session.add(row)
            session.commit()


def complete_part2(ticket_id: str, handoff: dict[str, Any], *, needs_human_review: bool) -> None:
    """Store the Part 3 handoff. The Part 1 routing_handoff is left unchanged."""
    with _WRITE_LOCK:
        with _session() as session:
            ticket = session.get(RfpTicket, ticket_id)
            if ticket is None:
                raise KeyError(ticket_id)
            ticket.part3_handoff = handoff
            ticket.part3_handoff_ready = True
            if needs_human_review:
                ticket.status = "needs_human_review"
            elif ticket.status in {"intake_complete", "drafting", "under_evaluation"}:
                ticket.status = "under_evaluation"
            ticket.updated_at = datetime.now(UTC)
            session.add(ticket)
            session.commit()
