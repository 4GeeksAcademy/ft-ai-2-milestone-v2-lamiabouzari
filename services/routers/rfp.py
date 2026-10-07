"""PDF upload and ticket status for RFP intake."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from data.pipelines.rfp_approval.decisions import ApprovalError
from data.pipelines.rfp_approval.pipeline import Part3NotReady, apply_arbitration, resume_approval, start_approval
from data.pipelines.rfp_intake.pipeline import process_ticket
from data.pipelines.rfp_intake.store import create_tables, create_ticket, get_engine, list_tickets, ticket_snapshot
from data.pipelines.rfp_response.pipeline import Part2NotReady, run_response
from dependencies import get_current_user
from models.user import UserPublic

router = APIRouter(prefix="/rfp", tags=["rfp"])

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RAW_DIR = _REPO_ROOT / "data" / "raw" / "rfp"
_MAX_BYTES = 10 * 1024 * 1024


def _ensure_store() -> None:
    try:
        get_engine()
        create_tables()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="RFP intake requires DATABASE_URL.") from exc


@router.post("/tickets", status_code=202)
async def upload_rfp(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    _user: UserPublic = Depends(get_current_user),
) -> dict[str, str]:
    """Create one analyzing ticket and run intake after the response is sent."""
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Upload a PDF file.")
    content = await file.read()
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="Upload a PDF file.")
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds the 10 MB limit.")
    _ensure_store()
    ticket_id = str(uuid.uuid4())
    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = _RAW_DIR / f"{ticket_id}.pdf"
    pdf_path.write_bytes(content)
    create_ticket(source_filename=filename, pdf_path=str(pdf_path), ticket_id=ticket_id)
    background.add_task(process_ticket, ticket_id)
    return {"ticket_id": ticket_id, "status": "analyzing"}


@router.get("/tickets")
def get_tickets(_user: UserPublic = Depends(get_current_user)) -> list[dict]:
    _ensure_store()
    snapshots = []
    for ticket in list_tickets():
        snapshot = ticket_snapshot(ticket.id)
        if snapshot is not None:
            snapshots.append(snapshot)
    return snapshots


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, _user: UserPublic = Depends(get_current_user)) -> dict:
    _ensure_store()
    snapshot = ticket_snapshot(ticket_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return snapshot


@router.post("/tickets/{ticket_id}/response")
def generate_response(ticket_id: str, _user: UserPublic = Depends(get_current_user)) -> dict:
    """Run Part 2 from the stored Part 1 routing handoff."""
    _ensure_store()
    try:
        return run_response(ticket_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    except Part2NotReady as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class ApprovalDecision(BaseModel):
    department: str
    decision: str
    actor: str
    comment: str = ""
    requested_changes: str | None = None


def _approval_http(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail="Ticket not found.")
    if isinstance(exc, Part3NotReady):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ApprovalError):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc


@router.post("/tickets/{ticket_id}/approval")
def open_approval(ticket_id: str, _user: UserPublic = Depends(get_current_user)) -> dict:
    """Open per-department approval interrupts from the persisted Part 2 drafts."""
    _ensure_store()
    try:
        return start_approval(ticket_id)
    except (KeyError, Part3NotReady, ApprovalError) as exc:
        raise _approval_http(exc) from exc


@router.post("/tickets/{ticket_id}/approval/resume")
def resume_department_approval(
    ticket_id: str,
    body: ApprovalDecision,
    _user: UserPublic = Depends(get_current_user),
) -> dict:
    """Apply one human decision and continue that department checkpoint only."""
    _ensure_store()
    try:
        return resume_approval(ticket_id, body.model_dump())
    except (KeyError, Part3NotReady, ApprovalError) as exc:
        raise _approval_http(exc) from exc


@router.post("/tickets/{ticket_id}/arbitration")
def arbitrate_ticket(ticket_id: str, _user: UserPublic = Depends(get_current_user)) -> dict:
    """Run the fixed arbitration rules against structured section state."""
    _ensure_store()
    try:
        result = apply_arbitration(ticket_id)
        snapshot = ticket_snapshot(ticket_id)
    except (KeyError, Part3NotReady, ApprovalError) as exc:
        raise _approval_http(exc) from exc
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return {"arbitration": result, "ticket": snapshot}


@router.get("/tickets/{ticket_id}/document")
def get_final_document(ticket_id: str, _user: UserPublic = Depends(get_current_user)) -> dict:
    _ensure_store()
    snapshot = ticket_snapshot(ticket_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    if snapshot.get("final_document") is None:
        raise HTTPException(status_code=404, detail="Final document is not ready.")
    return snapshot["final_document"]
