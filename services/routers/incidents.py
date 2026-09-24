"""Incident analysis and centralized incident manager routes."""
from __future__ import annotations
import csv, io
from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from fastapi import APIRouter, Body, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from tinydb import Query as TinyQuery
import database
from incident_analysis import REQUIRED_FIELDS, AnalysisReport, analyze_incidents
from models.incident import BRANCHES, CATEGORIES, ORIGINS, STATUSES, Incident, IncidentCreate, IncidentStatusUpdate, IncidentSummary
router = APIRouter(prefix="/api/incidents", tags=["incidents"])
_latest_report: AnalysisReport | None = None
TRANSITIONS = {"open": {"in_progress", "discarded"}, "in_progress": {"resolved", "discarded"}, "resolved": set(), "discarded": set()}

def _report_payload(report: AnalysisReport) -> dict[str, Any]:
    return {"total_records": report.total_records, "valid_records": report.valid_records, "invalid_records": report.invalid_records, "invalid_by_reason": report.invalid_by_reason, "category_breakdown": report.category_breakdown, "category_percentages": report.category_percentages, "status_breakdown": report.status_breakdown, "status_percentages": report.status_percentages, "country_breakdown": report.country_breakdown, "country_percentages": report.country_percentages, "closed_scored_incident_count": report.closed_scored_incident_count, "average_satisfaction": report.average_satisfaction, "score_distribution": {str(k): v for k, v in report.score_distribution.items()}}

def _parse_csv(contents: bytes) -> list[dict[str, str]]:
    try: text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as exc: raise HTTPException(400, "The CSV must be valid UTF-8.") from exc
    if not text.strip(): raise HTTPException(400, "The uploaded CSV is empty.")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames: raise HTTPException(400, "The CSV has no header row.")
    headers = [h.strip() if h else "" for h in reader.fieldnames]; missing = [f for f in REQUIRED_FIELDS if f not in headers]
    if missing: raise HTTPException(400, f"CSV is missing required columns: {', '.join(missing)}.")
    rows = []
    for row_number, row in enumerate(reader, 2):
        if None in row or any(value is None for value in row.values()): raise HTTPException(400, f"Malformed CSV at row {row_number}: inconsistent column count.")
        if any((value or "").strip() for value in row.values()): rows.append({key.strip(): value or "" for key, value in row.items() if key})
    if not rows: raise HTTPException(400, "The CSV contains no incident records.")
    return rows

def _validate(payload: dict[str, Any], model: Any) -> Any:
    try: return model.model_validate(payload)
    except Exception as exc:
        error = exc.errors()[0] if hasattr(exc, "errors") and exc.errors() else {"loc": ["request"], "msg": "Invalid request data."}
        field = str(error.get("loc", ["request"])[-1]); message = str(error.get("msg", "Invalid request data.")).replace("Value error, ", "")
        raise HTTPException(400, detail={"field": field, "message": message}) from None

@router.post("", status_code=201)
def create_incident(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    incident = _validate(payload, Incident); database.get_db().insert(incident.model_dump(mode="json")); return incident.model_dump(mode="json")
@router.get("")
def list_incidents(status_filter: str | None = Query(None, alias="status"), origin: str | None = None, branch: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    try:
        records = database.get_db().all()
    except Exception as exc:
        raise HTTPException(500, "Internal server error") from exc
    return [r for r in records if "title" in r and (not status_filter or r.get("status") == status_filter) and (not origin or r.get("origin") == origin) and (not branch or r.get("branch") == branch) and (not category or r.get("category") == category)]
@router.get("/summary", response_model=IncidentSummary)
def incident_summary() -> IncidentSummary:
    result = {"status": {x: 0 for x in STATUSES}, "category": {x: 0 for x in CATEGORIES}, "origin": {x: 0 for x in ORIGINS}, "branch": {x: 0 for x in BRANCHES}}
    for record in list_incidents():
        for group in result:
            if record.get(group) in result[group]: result[group][record[group]] += 1
    return IncidentSummary(**result)
@router.post("/analyze")
async def analyze_incident_file(file: UploadFile) -> dict[str, Any]:
    if not (file.filename or "").lower().endswith(".csv"): raise HTTPException(415, "Please upload a CSV file.")
    global _latest_report; _latest_report = analyze_incidents(_parse_csv(await file.read())); return _report_payload(_latest_report)
@router.get("/results/export")
def export_incident_results() -> StreamingResponse:
    if _latest_report is None: raise HTTPException(404, "No incident analysis is available. Analyze a CSV first.")
    output = io.StringIO(newline=""); writer = csv.writer(output); writer.writerow(["metric", "value", "percentage"]); writer.writerows([["total_records", _latest_report.total_records, ""], ["valid_records", _latest_report.valid_records, ""], ["invalid_records", _latest_report.invalid_records, ""]])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=trackflow-incident-results.csv"})

@router.get("/{incident_id}")
def get_incident(incident_id: UUID) -> dict[str, Any]:
    record = database.get_db().get(TinyQuery().id == str(incident_id))
    if not record or "title" not in record: raise HTTPException(404, "Incident not found")
    return record

@router.patch("/{incident_id}/status")
def update_incident_status(incident_id: UUID, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    update = _validate(payload, IncidentStatusUpdate); db = database.get_db(); record = db.get(TinyQuery().id == str(incident_id))
    if not record or "title" not in record: raise HTTPException(404, "Incident not found")
    current, target = record["status"], update.status.value
    if target not in TRANSITIONS[current]: raise HTTPException(400, detail={"field": "status", "message": f"Cannot move from {current} to {target}."})
    record["status"] = target; record["updated_at"] = datetime.now(UTC).isoformat(); db.update(record, TinyQuery().id == str(incident_id)); return record
