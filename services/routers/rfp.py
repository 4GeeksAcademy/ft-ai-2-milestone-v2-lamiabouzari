"""PDF upload and ticket status for RFP intake."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from data.pipelines.rfp_intake.pipeline import process_ticket
from data.pipelines.rfp_intake.store import create_tables, create_ticket, get_engine, list_tickets, ticket_snapshot
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
