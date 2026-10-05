"""Incident tool tests: lookup, creation, status update, scopes, backend errors."""

from __future__ import annotations

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import server

INCIDENT_ID = "11111111-1111-1111-1111-111111111111"

INCIDENT_RECORD = {
    "id": INCIDENT_ID,
    "title": "Late shipment",
    "description": "Order arrived three days late.",
    "category": "shipping",
    "status": "open",
    "origin": "customer",
    "branch": "los_angeles",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:read"]], indirect=True)
async def test_get_incident_success(authenticated, mock_backend) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/incidents/{INCIDENT_ID}"
        return httpx.Response(200, json=INCIDENT_RECORD)

    mock_backend(handler)

    async with Client(server.mcp) as client:
        result = await client.call_tool("get_incident", {"incident_id": INCIDENT_ID})

    assert result.data.title == "Late shipment"
    assert result.data.status == "open"


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:read"]], indirect=True)
async def test_get_incident_not_found(authenticated, mock_backend) -> None:
    mock_backend(lambda request: httpx.Response(404, json={"detail": "Incident not found"}))

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="NOT_FOUND"):
            await client.call_tool("get_incident", {"incident_id": INCIDENT_ID})


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:create"]], indirect=True)
async def test_get_incident_wrong_scope(authenticated, mock_backend) -> None:
    mock_backend(lambda request: httpx.Response(200, json=INCIDENT_RECORD))

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="Insufficient scope"):
            await client.call_tool("get_incident", {"incident_id": INCIDENT_ID})


@pytest.mark.asyncio
async def test_get_incident_unauthenticated(unauthenticated, mock_backend) -> None:
    mock_backend(lambda request: httpx.Response(200, json=INCIDENT_RECORD))

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="AUTHENTICATION_REQUIRED"):
            await client.call_tool("get_incident", {"incident_id": INCIDENT_ID})


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:create"]], indirect=True)
async def test_create_incident_success(authenticated, mock_backend) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/incidents"
        return httpx.Response(201, json=INCIDENT_RECORD)

    mock_backend(handler)

    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "create_incident",
            {
                "title": "Late shipment",
                "description": "Order arrived three days late.",
                "category": "shipping",
                "origin": "customer",
                "branch": "los_angeles",
            },
        )

    assert result.data.id == INCIDENT_ID


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:create"]], indirect=True)
async def test_create_incident_backend_validation_error(authenticated, mock_backend) -> None:
    mock_backend(
        lambda request: httpx.Response(
            400, json={"detail": {"field": "category", "message": "Invalid category"}}
        )
    )

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="VALIDATION_ERROR"):
            await client.call_tool(
                "create_incident",
                {
                    "title": "Late shipment",
                    "description": "Order arrived three days late.",
                    "category": "not-a-real-category",
                    "origin": "customer",
                    "branch": "los_angeles",
                },
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:update"]], indirect=True)
async def test_update_incident_status_success(authenticated, mock_backend) -> None:
    updated = {**INCIDENT_RECORD, "status": "in_progress"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/incidents/{INCIDENT_ID}/status"
        assert request.method == "PATCH"
        return httpx.Response(200, json=updated)

    mock_backend(handler)

    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "update_incident_status",
            {"incident_id": INCIDENT_ID, "status": "in_progress"},
        )

    assert result.data.status == "in_progress"


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:update"]], indirect=True)
async def test_update_incident_status_invalid_transition(authenticated, mock_backend) -> None:
    mock_backend(
        lambda request: httpx.Response(
            400, json={"detail": {"field": "status", "message": "Cannot move from resolved to open."}}
        )
    )

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="VALIDATION_ERROR"):
            await client.call_tool(
                "update_incident_status",
                {"incident_id": INCIDENT_ID, "status": "open"},
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:read"]], indirect=True)
async def test_get_incident_backend_timeout(authenticated, mock_backend) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("backend too slow", request=request)

    mock_backend(handler)

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="BACKEND_TIMEOUT"):
            await client.call_tool("get_incident", {"incident_id": INCIDENT_ID})


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:read"]], indirect=True)
async def test_get_incident_backend_service_error(authenticated, mock_backend) -> None:
    mock_backend(lambda request: httpx.Response(500, text="boom"))

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="BACKEND_ERROR"):
            await client.call_tool("get_incident", {"incident_id": INCIDENT_ID})


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:read"]], indirect=True)
async def test_get_incident_invalid_uuid_rejected_before_backend_call(authenticated, mock_backend) -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json=INCIDENT_RECORD)

    mock_backend(handler)

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="VALIDATION_ERROR"):
            await client.call_tool("get_incident", {"incident_id": "not-a-uuid"})

    assert called is False
