"""Telemetry ingestion routes."""

import logging

from fastapi import APIRouter

from models.telemetry import TelemetryBatch

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger(__name__)


@router.post("/events")
def receive_events(batch: TelemetryBatch) -> dict[str, int]:
    """Accept telemetry in memory and acknowledge the received count."""
    logger.info("Received %d telemetry events", len(batch.events))
    for event in batch.events:
        logger.info("Received telemetry event_type=%s", event.event_type)

    return {"received": len(batch.events)}