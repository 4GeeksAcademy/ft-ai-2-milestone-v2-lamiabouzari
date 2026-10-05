"""Tool invocation logging behavior."""

from __future__ import annotations

import logging

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
async def test_successful_call_is_logged_with_tool_subject_and_outcome(
    authenticated, mock_backend, caplog: pytest.LogCaptureFixture
) -> None:
    mock_backend(lambda request: httpx.Response(200, json=INCIDENT_RECORD))

    with caplog.at_level(logging.INFO, logger="mcps.tools"):
        async with Client(server.mcp) as client:
            await client.call_tool("get_incident", {"incident_id": INCIDENT_ID})

    [record] = [r for r in caplog.records if r.name == "mcps.tools"]
    message = record.getMessage()
    assert "tool=get_incident" in message
    assert f"subject={authenticated.subject}" in message
    assert "outcome=success" in message
    assert "timestamp=" in message
    # Never log the raw bearer token.
    assert authenticated.token not in message


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:read"]], indirect=True)
async def test_failed_call_is_logged_with_error_outcome(
    authenticated, mock_backend, caplog: pytest.LogCaptureFixture
) -> None:
    mock_backend(lambda request: httpx.Response(404, json={"detail": "not found"}))

    with caplog.at_level(logging.INFO, logger="mcps.tools"):
        async with Client(server.mcp) as client:
            with pytest.raises(ToolError):
                await client.call_tool("get_incident", {"incident_id": INCIDENT_ID})

    [record] = [r for r in caplog.records if r.name == "mcps.tools"]
    message = record.getMessage()
    assert "outcome=error" in message
    assert "error_type=" in message
