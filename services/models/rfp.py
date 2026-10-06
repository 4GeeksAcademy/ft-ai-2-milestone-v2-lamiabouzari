"""SQLModel tables for RFP intake. Postgres is the source of truth."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

TicketStatus = str  # analyzing | intake_complete | discarded


def _now() -> datetime:
    return datetime.now(UTC)


class RfpTicket(SQLModel, table=True):
    """One uploaded PDF and the intake status for that ticket."""

    __tablename__ = "rfp_tickets"

    id: str = Field(primary_key=True)
    status: str = "analyzing"
    source_filename: str
    pdf_path: str
    markdown_text: str | None = None
    discard_reason: str | None = None
    error_message: str | None = None
    intake_failed: bool = False
    currency_context: str | None = None
    handoff_ready: bool = False
    routing_handoff: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class RfpMetadataRecord(SQLModel, table=True):
    """Extracted client facts and readability for one ticket."""

    __tablename__ = "rfp_metadata"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_tickets.id", unique=True)
    client_name: str | None = None
    client_country: str | None = None
    services_requested: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    monthly_volume: str | None = None
    deadline: str | None = None
    budget_range: str | None = None
    departments_needed: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    currency_context: str = "UNKNOWN"
    readability: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    is_rfp: bool = False
    document_style: str = "not_applicable"
    classification_reason: str = ""


class RfpDepartmentSection(SQLModel, table=True):
    """One department worker result, including key aspects."""

    __tablename__ = "rfp_department_sections"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_tickets.id")
    department_key: str
    department_name: str
    contact: str
    key_aspects: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    open_questions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    extract_text: str = ""


class RfpSynthesizerRecord(SQLModel, table=True):
    """Sales-facing synthesis and the Part 2 handoff payload."""

    __tablename__ = "rfp_synthesizer_results"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_tickets.id", unique=True)
    sales_summary: str
    payload: dict[str, Any] = Field(sa_column=Column(JSON))
