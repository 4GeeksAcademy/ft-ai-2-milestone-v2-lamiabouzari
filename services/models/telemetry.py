"""Pydantic models for the telemetry ingestion contract."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


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


class TelemetryEventRecord(SQLModel, table=True):
    """Immutable telemetry row stored in PostgreSQL."""

    __tablename__ = "telemetry_events"
    __table_args__ = (
        Index("ix_telemetry_events_timestamp", "timestamp"),
        Index("ix_telemetry_events_event_type", "event_type"),
        Index(
            "ix_telemetry_events_tags_gin",
            "tags",
            postgresql_using="gin",
        ),
    )

    event_id: uuid.UUID = SQLField(primary_key=True)
    timestamp: datetime
    session_id: uuid.UUID
    user_id: str
    event_type: str
    schema_version: str
    request_id: uuid.UUID | None = None
    tags: dict[str, Any] = SQLField(sa_column=Column(JSONB, nullable=False))