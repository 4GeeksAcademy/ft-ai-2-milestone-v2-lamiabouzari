"""Deprecated: direct (non-MCP) incident lookup, kept only as legacy code.

No longer imported by the support agent — ``data/pipelines/support_agent.py``
now reaches incidents exclusively through ``data/pipelines/mcp_tools.py`` and
the MCP server in ``mcps/``. This module reads the same TinyDB store used by
``services/routers/incidents.py`` directly and is unused outside its own
tests; retained for reference rather than deleted.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from tinydb import Query as TinyQuery

import database

DEFAULT_LOOKUP_TIMEOUT_SECONDS = 5.0

_UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def extract_incident_id(text: str) -> str | None:
    """Pull the first UUID-looking token out of free-form text, if any."""
    match = _UUID_PATTERN.search(text)
    return match.group(0) if match else None


class IncidentLookupTimeout(Exception):
    """Raised when the incident manager does not respond within the timeout."""


class IncidentLookupInput(BaseModel):
    """Typed request for a single incident lookup, plus optional list filters."""

    incident_id: str = Field(min_length=1)
    status_filter: str | None = None
    origin: str | None = None
    branch: str | None = None
    category: str | None = None

    @field_validator("incident_id")
    @classmethod
    def _valid_uuid(cls, value: str) -> str:
        try:
            UUID(value)
        except ValueError as exc:
            raise ValueError("incident_id must be a valid UUID") from exc
        return value


class IncidentLookupResult(BaseModel):
    """Only the real fields exposed by the incident service — never invented."""

    found: bool
    incident_id: str | None = None
    status: str | None = None
    category: str | None = None
    origin: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    error: str | None = None


def _as_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _read_incident_record(incident_id: str) -> dict[str, Any] | None:
    """Query the live incident store directly — the same data the router reads."""
    record = database.get_db().get(TinyQuery().id == incident_id)
    if not record or "title" not in record:
        return None
    return record


def _run_with_timeout(timeout: float, incident_id: str) -> dict[str, Any] | None:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_read_incident_record, incident_id)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError as exc:
            raise IncidentLookupTimeout(
                f"Incident manager lookup for {incident_id} timed out after {timeout}s."
            ) from exc


def lookup_incident(
    request: IncidentLookupInput,
    *,
    timeout: float = DEFAULT_LOOKUP_TIMEOUT_SECONDS,
) -> IncidentLookupResult:
    """Read-only lookup against the real incident manager. Never writes data."""
    try:
        record = _run_with_timeout(timeout, request.incident_id)
    except IncidentLookupTimeout:
        return IncidentLookupResult(
            found=False,
            incident_id=request.incident_id,
            error="timeout",
        )
    except Exception:
        return IncidentLookupResult(
            found=False,
            incident_id=request.incident_id,
            error="error",
        )

    if record is None:
        return IncidentLookupResult(
            found=False,
            incident_id=request.incident_id,
            error="not_found",
        )

    return IncidentLookupResult(
        found=True,
        incident_id=request.incident_id,
        status=record.get("status"),
        category=record.get("category"),
        origin=record.get("origin"),
        created_at=_as_iso(record.get("created_at")),
        updated_at=_as_iso(record.get("updated_at")),
    )
