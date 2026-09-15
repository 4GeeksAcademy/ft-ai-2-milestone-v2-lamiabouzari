"""Telemetry ingestion routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import insert
from sqlmodel import Session

from database import get_inventory_db
from models.telemetry import TelemetryEvent, TelemetryEventRecord

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger(__name__)


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