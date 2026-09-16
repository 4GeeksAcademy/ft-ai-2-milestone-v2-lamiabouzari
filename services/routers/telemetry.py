"""Telemetry ingestion routes."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import insert
from sqlmodel import Session

from database import get_inventory_db
from models.telemetry import TelemetryEvent, TelemetryEventRecord
from telemetry.analysis import generate_report

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Existing: POST /telemetry/events
# ---------------------------------------------------------------------------


@router.post("/events")
def receive_events(
    payload: dict[str, Any],
    session: Session = Depends(get_inventory_db),
) -> dict[str, int]:
    """Validate and persist a batch of telemetry events atomically."""
    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        # Keep the body loose so malformed individual events can be handled
        # below, while still requiring the documented envelope shape.
        raise HTTPException(status_code=422, detail="events must be a list")

    valid_records: list[TelemetryEventRecord] = []
    rejected = 0
    for raw_event in raw_events:
        try:
            event = TelemetryEvent.model_validate(raw_event)
        except ValidationError:
            rejected += 1
            continue

        logger.info("Received telemetry event_type=%s", event.event_type)
        valid_records.append(
            TelemetryEventRecord(
                event_id=event.eventId,
                timestamp=event.timestamp,
                session_id=event.sessionId,
                user_id=event.userId,
                event_type=event.event_type,
                schema_version=event.schemaVersion,
                request_id=event.requestId,
                tags=event.properties,
            )
        )

    if valid_records:
        # One execute call and one commit means the complete valid batch is a
        # single database transaction; a failure rolls back the whole batch.
        session.execute(
            insert(TelemetryEventRecord),
            [record.model_dump() for record in valid_records],
        )
        session.commit()

    return {
        "received": len(raw_events),
        "stored": len(valid_records),
        "rejected": rejected,
    }


# ---------------------------------------------------------------------------
# New: GET /telemetry/report
# ---------------------------------------------------------------------------


def _parse_date(date_str: str | None, default: datetime) -> datetime:
    """Parse an ISO 8601 date string or return the default.

    Accepts both ``YYYY-MM-DD`` and full ISO 8601 with time and offset.
    """
    if date_str is None:
        return default
    try:
        dt = datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date: '{date_str}'. Expected ISO 8601 format "
            f"(e.g. '2026-09-10' or '2026-09-10T12:00:00Z').",
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


@router.get("/report")
def telemetry_report(
    start_date: str | None = Query(
        default=None,
        description="Start of the report window (ISO 8601). Defaults to 7 days ago UTC.",
    ),
    end_date: str | None = Query(
        default=None,
        description="End of the report window (ISO 8601). Defaults to now UTC.",
    ),
    session: Session = Depends(get_inventory_db),
) -> dict[str, Any]:
    """Generate a telemetry technical report for the given date window.

    Returns three operational metrics computed from the telemetry events that
    occurred within the window:
      - ``api_failures_by_endpoint``
      - ``auth_security_signals``
      - ``frontend_performance``

    Results are cached in-memory for 60 seconds.
    """
    now = datetime.now(UTC)
    window_end = _parse_date(end_date, now)
    window_start = _parse_date(start_date, now - timedelta(days=7))

    if window_end < window_start:
        raise HTTPException(
            status_code=400,
            detail=f"end_date ({window_end.isoformat()}) is before "
            f"start_date ({window_start.isoformat()}).",
        )

    metrics = generate_report(session, window_start, window_end)

    return {
        "period": {
            "from": window_start.isoformat(),
            "to": window_end.isoformat(),
        },
        "metrics": metrics,
    }