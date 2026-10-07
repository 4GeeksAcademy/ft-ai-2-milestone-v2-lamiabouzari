"""SQLModel tables for RFP intake. Postgres is the source of truth."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

# Part 1: analyzing | intake_complete | discarded
# Part 2: drafting | under_evaluation | needs_human_review
# Part 3: waiting_for_approval | done
TicketStatus = str


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
    part3_handoff_ready: bool = False
    part3_handoff: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    open_conflicts: list[Any] | None = Field(default=None, sa_column=Column(JSON))
    arbitration_iterations: int = 0
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
    """One department worker result, plus the Part 2 draft and evaluation."""

    __tablename__ = "rfp_department_sections"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_tickets.id")
    department_key: str
    department_name: str
    contact: str
    key_aspects: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    open_questions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    extract_text: str = ""
    draft_content: str = ""
    evaluation_results: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    iteration_count: int = 0
    section_status: str | None = None
    approval_status: str | None = None
    needs_human_review: bool = False


class RfpApprovalCheckpoint(SQLModel, table=True):
    """Durable per-department approval interrupt. One row per thread_id."""

    __tablename__ = "rfp_approval_checkpoints"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_tickets.id", index=True)
    department_key: str
    thread_id: str = Field(unique=True, index=True)
    node: str = "approval_interrupt"
    interrupted: bool = True
    revision_count: int = 0
    state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=_now)


class RfpTraceRecord(SQLModel, table=True):
    """Ordered record of Part 3 nodes. This is the trace, not a server log."""

    __tablename__ = "rfp_traces"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_tickets.id", index=True)
    ts: datetime = Field(default_factory=_now)
    agent: str
    department: str | None = None
    input_ref: str = ""
    output_ref: str = ""
    action: str


class RfpFinalDocument(SQLModel, table=True):
    """Approved proposal stored for Sales. Written before the ticket is done."""

    __tablename__ = "rfp_final_documents"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_tickets.id", unique=True)
    document_markdown: str
    client_name: str | None = None
    client_country: str | None = None
    currency_context: str | None = None
    approved_sections: list[Any] = Field(default_factory=list, sa_column=Column(JSON))
    approvers: list[Any] = Field(default_factory=list, sa_column=Column(JSON))
    generated_at: datetime = Field(default_factory=_now)
    trace_ref: str | None = None


class RfpSynthesizerRecord(SQLModel, table=True):
    """Sales-facing synthesis and the Part 2 handoff payload."""

    __tablename__ = "rfp_synthesizer_results"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_tickets.id", unique=True)
    sales_summary: str
    payload: dict[str, Any] = Field(sa_column=Column(JSON))
