"""Incident Manager MCP tools — backed by the real TrackFlow Incident API.

These tools call `services/routers/incidents.py` over HTTP; no parallel
incident dataset or status-transition logic is implemented here. The backend
remains the single source of truth for validation (allowed categories,
origins, branches) and status-transition rules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field

from auth import require_scope
from backend_client import request_json
from errors import RequestValidationFailedError
from logging_config import log_tool_invocation

if TYPE_CHECKING:
    from fastmcp import FastMCP


class IncidentResult(BaseModel):
    """Structured incident payload mirroring `services.models.incident.Incident`."""

    id: str
    title: str
    description: str
    category: str
    status: str
    origin: str
    branch: str
    created_at: str
    updated_at: str


def _validate_uuid(value: str, *, field: str = "incident_id") -> None:
    try:
        UUID(value)
    except ValueError as exc:
        raise RequestValidationFailedError(f"'{value}' is not a valid UUID for '{field}'.") from exc


def register(mcp: "FastMCP") -> None:
    """Register incident tools on the given FastMCP server instance."""

    @mcp.tool(
        name="get_incident",
        description=(
            "Fetch a single TrackFlow incident by ID via GET /api/incidents/{incident_id}. "
            "Read-only. Requires the 'incidents:read' scope."
        ),
        run_in_thread=False,
    )
    async def get_incident(
        incident_id: Annotated[str, Field(description="UUID of the incident to fetch.")],
    ) -> IncidentResult:
        auth_info = require_scope("incidents:read")
        with log_tool_invocation("get_incident", auth_info.subject):
            _validate_uuid(incident_id)
            data: dict[str, Any] = await request_json("GET", f"/api/incidents/{incident_id}")
            return IncidentResult.model_validate(data)

    @mcp.tool(
        name="create_incident",
        description=(
            "Create a new TrackFlow incident via POST /api/incidents. "
            "Requires the 'incidents:create' scope."
        ),
        run_in_thread=False,
    )
    async def create_incident(
        title: Annotated[str, Field(min_length=1, max_length=200, description="Short incident title.")],
        description: Annotated[
            str, Field(min_length=1, max_length=5000, description="Full incident description.")
        ],
        category: Annotated[
            str, Field(description="Incident category. Must match one of the backend's valid categories.")
        ],
        origin: Annotated[
            str, Field(description="Where the incident originated: 'customer', 'branch', or 'internal'.")
        ],
        branch: Annotated[
            str, Field(description="Branch involved: 'los_angeles', 'zaragoza', or 'central'.")
        ],
    ) -> IncidentResult:
        auth_info = require_scope("incidents:create")
        with log_tool_invocation("create_incident", auth_info.subject):
            payload = {
                "title": title,
                "description": description,
                "category": category,
                "origin": origin,
                "branch": branch,
            }
            data = await request_json("POST", "/api/incidents", json=payload)
            return IncidentResult.model_validate(data)

    @mcp.tool(
        name="update_incident_status",
        description=(
            "Transition a TrackFlow incident's status via "
            "PATCH /api/incidents/{incident_id}/status. "
            "Requires the 'incidents:update' scope. The backend enforces the "
            "allowed status transitions (e.g. 'open' -> 'in_progress' or 'discarded')."
        ),
        run_in_thread=False,
    )
    async def update_incident_status(
        incident_id: Annotated[str, Field(description="UUID of the incident to update.")],
        status: Annotated[
            str,
            Field(description="New status: 'open', 'in_progress', 'resolved', or 'discarded'."),
        ],
    ) -> IncidentResult:
        auth_info = require_scope("incidents:update")
        with log_tool_invocation("update_incident_status", auth_info.subject):
            _validate_uuid(incident_id)
            data = await request_json(
                "PATCH",
                f"/api/incidents/{incident_id}/status",
                json={"status": status},
            )
            return IncidentResult.model_validate(data)
