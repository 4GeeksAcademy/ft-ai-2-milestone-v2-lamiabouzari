"""Pydantic models for the telemetry ingestion contract."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TelemetryEvent(BaseModel):
    """Standard TrackFlow telemetry event envelope."""

    model_config = ConfigDict(extra="forbid")

    eventId: uuid.UUID
    timestamp: datetime
    sessionId: uuid.UUID
    userId: str
    event_type: str
    schemaVersion: str
    requestId: uuid.UUID | None
    properties: dict[str, Any]


class TelemetryBatch(BaseModel):
    """Batch submitted by the frontend telemetry service."""

    model_config = ConfigDict(extra="forbid")

    events: list[TelemetryEvent]