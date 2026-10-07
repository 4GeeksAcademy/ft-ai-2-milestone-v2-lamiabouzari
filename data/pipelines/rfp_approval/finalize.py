"""Final document. Stored before the ticket status becomes done."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session

from data.pipelines.rfp_approval.arbitrate import detect_conflicts
from data.pipelines.rfp_approval.checkpointer import set_ticket_fields
from data.pipelines.rfp_approval.trace import record_trace
from data.pipelines.rfp_intake.departments import DEPARTMENT_ORDER
from data.pipelines.rfp_intake.store import get_engine, ticket_snapshot
from models.rfp import RfpFinalDocument


def persist_document(ticket_id: str, document: dict[str, Any]) -> int:
    """Commit the artifact by itself. Status is updated only after this returns."""
    row = RfpFinalDocument(
        ticket_id=ticket_id,
        document_markdown=document["document_markdown"],
        client_name=document.get("client_name"),
        client_country=document.get("client_country"),
        currency_context=document.get("currency_context"),
        approved_sections=document["approved_sections"],
        approvers=document["approvers"],
        generated_at=datetime.now(UTC),
        trace_ref=document.get("trace_ref"),
    )
    with Session(get_engine(), expire_on_commit=False) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        if row.id is None:
            raise RuntimeError("Final document was not stored.")
        return row.id


def _ordered(active: list[str]) -> list[str]:
    rank = {key: index for index, key in enumerate(DEPARTMENT_ORDER)}
    return sorted(active, key=lambda key: rank.get(key, 99))


def finalize_if_ready(ticket_id: str) -> dict[str, Any] | None:
    """Write the final document only when every active department is approved and compliant."""
    snapshot = ticket_snapshot(ticket_id)
    if snapshot is None or snapshot["status"] != "waiting_for_approval":
        return None
    active = [item["department_id"] for item in (snapshot.get("part3_handoff") or {}).get("departments") or []]
    approvals = {item["department_id"]: item for item in snapshot.get("approvals") or []}
    if not active or any(department not in approvals for department in active):
        return None
    blocked = [
        department
        for department in active
        if approvals[department]["approval_status"] != "approved" or approvals[department]["interrupted"]
    ]
    if blocked:
        return None
    country = (snapshot.get("metadata") or {}).get("client_country")
    sections = [
        {"department_id": department, "draft_content": approvals[department]["draft_content"]}
        for department in active
    ]
    conflicts = detect_conflicts(sections, country)
    if conflicts:
        set_ticket_fields(ticket_id, open_conflicts=conflicts)
        record_trace(
            ticket_id,
            "final_synthesis",
            "blocked",
            input_ref="approved-sections",
            output_ref=",".join(item["conflict_id"] for item in conflicts),
        )
        return None

    metadata = snapshot.get("metadata") or {}
    currency = snapshot.get("currency_context") or metadata.get("currency_context")
    pieces = [
        "# TrackFlow proposal",
        "",
        f"Ticket: {ticket_id}",
        f"Client: {metadata.get('client_name') or 'Not stated'}",
        f"Country: {metadata.get('client_country') or 'Not stated'}",
        f"Currency: {currency or 'Not stated'}",
        "",
    ]
    approved_sections = []
    approvers = []
    for department in _ordered(active):
        approval = approvals[department]
        pieces.extend(
            [
                f"## {approval.get('department_name') or department}",
                "",
                f"Approver: {approval.get('owner')}",
                "",
                approval["draft_content"].strip(),
                "",
            ]
        )
        approved_sections.append(
            {
                "department_id": department,
                "owner": approval.get("owner"),
                "draft_content": approval["draft_content"],
            }
        )
        approvers.append({"department_id": department, "actor": approval.get("owner"), "comment": approval.get("comment")})
    document = {
        "document_markdown": "\n".join(pieces).strip() + "\n",
        "client_name": metadata.get("client_name"),
        "client_country": metadata.get("client_country"),
        "currency_context": currency,
        "approved_sections": approved_sections,
        "approvers": approvers,
        "trace_ref": f"rfp-traces:{ticket_id}",
    }
    document_id = persist_document(ticket_id, document)
    set_ticket_fields(ticket_id, status="done", open_conflicts=[])
    record_trace(
        ticket_id,
        "final_synthesis",
        "stored",
        input_ref="approved-sections",
        output_ref=f"final_document:{document_id}",
    )
    return ticket_snapshot(ticket_id)
