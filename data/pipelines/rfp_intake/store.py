"""Persistence for RFP tickets through the existing SQLModel engine."""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SERVICES = Path(__file__).resolve().parents[3] / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

from models.rfp import (
    RfpDepartmentSection,
    RfpMetadataRecord,
    RfpSynthesizerRecord,
    RfpTicket,
)

_engine: Engine | None = None

HANDOFF_CONTRACT = "trackflow.rfp.intake.v1"
PART1_STATUSES = ("analyzing", "intake_complete", "discarded")


def set_engine(engine: Engine | None) -> None:
    """Point intake persistence at a test engine. None uses the app engine."""
    global _engine
    _engine = engine


def get_engine() -> Engine:
    if _engine is not None:
        return _engine
    from database import get_inventory_engine

    return get_inventory_engine()


def create_tables(engine: Engine | None = None) -> None:
    target = engine or get_engine()
    SQLModel.metadata.create_all(
        target,
        tables=[
            RfpTicket.__table__,
            RfpMetadataRecord.__table__,
            RfpDepartmentSection.__table__,
            RfpSynthesizerRecord.__table__,
        ],
    )


def _session() -> Session:
    return Session(get_engine(), expire_on_commit=False)


def _touch(ticket: RfpTicket) -> None:
    ticket.updated_at = datetime.now(UTC)


def create_ticket(*, source_filename: str, pdf_path: str, ticket_id: str | None = None) -> RfpTicket:
    """Insert one ticket in analyzing. Upload returns before the pipeline runs."""
    ticket = RfpTicket(
        id=ticket_id or str(uuid.uuid4()),
        status="analyzing",
        source_filename=source_filename,
        pdf_path=pdf_path,
    )
    with _session() as session:
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        return ticket


def get_ticket(ticket_id: str) -> RfpTicket | None:
    with _session() as session:
        return session.get(RfpTicket, ticket_id)


def list_tickets() -> list[RfpTicket]:
    with _session() as session:
        rows = session.exec(select(RfpTicket).order_by(RfpTicket.created_at.desc())).all()
        return list(rows)


def save_markdown(ticket_id: str, markdown: str) -> None:
    with _session() as session:
        ticket = session.get(RfpTicket, ticket_id)
        if ticket is None:
            raise KeyError(ticket_id)
        ticket.markdown_text = markdown
        _touch(ticket)
        session.add(ticket)
        session.commit()


def mark_discarded(ticket_id: str, reason: str) -> None:
    with _session() as session:
        ticket = session.get(RfpTicket, ticket_id)
        if ticket is None:
            raise KeyError(ticket_id)
        ticket.status = "discarded"
        ticket.discard_reason = reason
        ticket.handoff_ready = False
        ticket.routing_handoff = None
        ticket.error_message = None
        ticket.intake_failed = False
        _touch(ticket)
        session.add(ticket)
        session.commit()


def mark_intake_complete(ticket_id: str, *, currency_context: str, handoff: dict[str, Any]) -> None:
    with _session() as session:
        ticket = session.get(RfpTicket, ticket_id)
        if ticket is None:
            raise KeyError(ticket_id)
        ticket.status = "intake_complete"
        ticket.currency_context = currency_context
        ticket.handoff_ready = True
        ticket.routing_handoff = handoff
        ticket.discard_reason = None
        ticket.error_message = None
        ticket.intake_failed = False
        _touch(ticket)
        session.add(ticket)
        session.commit()


def record_error(ticket_id: str, message: str) -> None:
    """Stop a crashed job from looking in progress.

    Part 1 status stays ``analyzing``. ``intake_failed`` and ``error_message``
    are the pollable failure signal. The handoff is not marked ready.
    """
    with _session() as session:
        ticket = session.get(RfpTicket, ticket_id)
        if ticket is None:
            return
        ticket.error_message = message[:1000]
        ticket.intake_failed = True
        ticket.handoff_ready = False
        ticket.routing_handoff = None
        _touch(ticket)
        session.add(ticket)
        session.commit()


def save_metadata(ticket_id: str, values: dict[str, Any]) -> None:
    with _session() as session:
        existing = session.exec(
            select(RfpMetadataRecord).where(RfpMetadataRecord.ticket_id == ticket_id)
        ).first()
        record = existing or RfpMetadataRecord(ticket_id=ticket_id)
        for key, value in values.items():
            setattr(record, key, value)
        session.add(record)
        session.commit()


def replace_sections(ticket_id: str, sections: list[dict[str, Any]]) -> None:
    with _session() as session:
        current = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).all()
        for row in current:
            session.delete(row)
        for section in sections:
            session.add(RfpDepartmentSection(ticket_id=ticket_id, **section))
        session.commit()


def save_synthesizer(ticket_id: str, sales_summary: str, payload: dict[str, Any]) -> None:
    with _session() as session:
        existing = session.exec(
            select(RfpSynthesizerRecord).where(RfpSynthesizerRecord.ticket_id == ticket_id)
        ).first()
        record = existing or RfpSynthesizerRecord(
            ticket_id=ticket_id,
            sales_summary=sales_summary,
            payload=payload,
        )
        record.sales_summary = sales_summary
        record.payload = payload
        session.add(record)
        session.commit()


def ticket_snapshot(ticket_id: str) -> dict[str, Any] | None:
    """Read ticket, metadata, sections, and synthesizer in one view."""
    with _session() as session:
        ticket = session.get(RfpTicket, ticket_id)
        if ticket is None:
            return None
        metadata = session.exec(
            select(RfpMetadataRecord).where(RfpMetadataRecord.ticket_id == ticket_id)
        ).first()
        sections = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).all()
        synthesis = session.exec(
            select(RfpSynthesizerRecord).where(RfpSynthesizerRecord.ticket_id == ticket_id)
        ).first()
        return {
            "ticket_id": ticket.id,
            "status": ticket.status,
            "source_filename": ticket.source_filename,
            "discard_reason": ticket.discard_reason,
            "error_message": ticket.error_message,
            "intake_failed": ticket.intake_failed,
            "currency_context": ticket.currency_context,
            "handoff_ready": ticket.handoff_ready,
            "routing_handoff": ticket.routing_handoff,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
            "metadata": _metadata_payload(metadata),
            "sections": [_section_payload(section) for section in sections],
            "synthesizer": None
            if synthesis is None
            else {"sales_summary": synthesis.sales_summary, "payload": synthesis.payload},
        }


def _metadata_payload(record: RfpMetadataRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "client_name": record.client_name,
        "client_country": record.client_country,
        "services_requested": record.services_requested or [],
        "monthly_volume": record.monthly_volume,
        "deadline": record.deadline,
        "budget_range": record.budget_range,
        "departments_needed": record.departments_needed or [],
        "currency_context": record.currency_context,
        "readability": record.readability or {},
        "is_rfp": record.is_rfp,
        "document_style": record.document_style,
        "classification_reason": record.classification_reason,
    }


def _section_payload(section: RfpDepartmentSection) -> dict[str, Any]:
    return {
        "department_key": section.department_key,
        "department_name": section.department_name,
        "contact": section.contact,
        "key_aspects": section.key_aspects or [],
        "open_questions": section.open_questions or [],
    }
