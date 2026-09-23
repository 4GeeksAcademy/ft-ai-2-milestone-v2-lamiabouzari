"""TrackFlow incident analysis API routes."""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from incident_analysis import REQUIRED_FIELDS, AnalysisReport, analyze_incidents

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

_latest_report: AnalysisReport | None = None


def _report_payload(report: AnalysisReport) -> dict[str, Any]:
    """Serialize only aggregate analysis data; never include source rows."""
    return {
        "total_records": report.total_records,
        "valid_records": report.valid_records,
        "invalid_records": report.invalid_records,
        "invalid_by_reason": report.invalid_by_reason,
        "category_breakdown": report.category_breakdown,
        "category_percentages": report.category_percentages,
        "status_breakdown": report.status_breakdown,
        "status_percentages": report.status_percentages,
        "country_breakdown": report.country_breakdown,
        "country_percentages": report.country_percentages,
        "closed_scored_incident_count": report.closed_scored_incident_count,
        "average_satisfaction": report.average_satisfaction,
        "score_distribution": {
            str(score): count for score, count in report.score_distribution.items()
        },
    }


def _parse_csv(contents: bytes) -> list[dict[str, str]]:
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="The CSV must be valid UTF-8.") from exc
    if not text.strip():
        raise HTTPException(status_code=400, detail="The uploaded CSV is empty.")

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="The CSV has no header row.")
    headers = [header.strip() if header else "" for header in reader.fieldnames]
    missing = [field for field in REQUIRED_FIELDS if field not in headers]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required columns: {', '.join(missing)}.",
        )

    rows: list[dict[str, str]] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row or any(value is None for value in row.values()):
            raise HTTPException(
                status_code=400,
                detail=f"Malformed CSV at row {row_number}: inconsistent column count.",
            )
        if not any((value or "").strip() for value in row.values()):
            continue
        rows.append({key.strip(): value or "" for key, value in row.items() if key})
    if not rows:
        raise HTTPException(status_code=400, detail="The CSV contains no incident records.")
    return rows


@router.post("/analyze")
async def analyze_incident_file(file: UploadFile) -> dict[str, Any]:
    """Validate and aggregate a TrackFlow incident CSV."""
    filename = file.filename or ""
    content_type = (file.content_type or "").lower()
    allowed_types = {"text/csv", "application/csv", "application/vnd.ms-excel", "application/octet-stream"}
    if not filename.lower().endswith(".csv") or (content_type and content_type not in allowed_types):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Please upload a CSV file.",
        )
    contents = await file.read()
    rows = _parse_csv(contents)
    report = analyze_incidents(rows)

    global _latest_report
    _latest_report = report
    return _report_payload(report)


def _export_rows(report: AnalysisReport) -> list[tuple[str, object, object]]:
    rows: list[tuple[str, object, object]] = [
        ("total_records", report.total_records, ""),
        ("valid_records", report.valid_records, ""),
        ("invalid_records", report.invalid_records, ""),
        ("closed_scored_incident_count", report.closed_scored_incident_count, ""),
        ("average_satisfaction", report.average_satisfaction or "", ""),
    ]
    for reason, value in report.invalid_by_reason.items():
        rows.append((f"invalid_by_reason.{reason}", value, ""))
    for name, counts, percentages in (
        ("category", report.category_breakdown, report.category_percentages),
        ("status", report.status_breakdown, report.status_percentages),
        ("country", report.country_breakdown, report.country_percentages),
    ):
        for key, value in counts.items():
            rows.append((f"{name}.{key}", value, percentages.get(key, "")))
    for score, value in report.score_distribution.items():
        rows.append((f"score_distribution.{score}", value, ""))
    return rows


@router.get("/results/export")
def export_incident_results() -> StreamingResponse:
    """Download the latest aggregate-only incident analysis."""
    if _latest_report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No incident analysis is available. Analyze a CSV first.",
        )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["metric", "value", "percentage"])
    writer.writerows(_export_rows(_latest_report))
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trackflow-incident-results.csv"},
    )
