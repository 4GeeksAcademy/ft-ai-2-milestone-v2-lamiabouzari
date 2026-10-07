"""Append-only Part 3 trace."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session

from data.pipelines.rfp_intake.store import get_engine
from models.rfp import RfpTraceRecord


def record_trace(
    ticket_id: str,
    agent: str,
    action: str,
    *,
    department: str | None = None,
    input_ref: str = "",
    output_ref: str = "",
) -> None:
    row = RfpTraceRecord(
        ticket_id=ticket_id,
        ts=datetime.now(UTC),
        agent=agent,
        department=department,
        input_ref=input_ref[:500],
        output_ref=output_ref[:500],
        action=action,
    )
    with Session(get_engine(), expire_on_commit=False) as session:
        session.add(row)
        session.commit()
