"""HTTP-level tests for the mcpauth bearer-auth middleware itself.

Exercises the real ASGI app (`server.app`), not the in-process tool shortcut,
to prove requests without a bearer token are rejected by mcpauth before ever
reaching a tool.
"""

from __future__ import annotations

import httpx
import pytest

import server


@pytest.mark.asyncio
async def test_missing_bearer_token_is_rejected_with_401() -> None:
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.test") as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 401
    body = response.json()
    assert body["error"] == "missing_auth_header"
    assert "Authorization: Bearer " not in str(body)


@pytest.mark.asyncio
async def test_get_mcp_without_bearer_token_is_rejected() -> None:
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.test") as client:
        response = await client.get("/mcp")

    assert response.status_code == 401
    assert response.json()["error"] == "missing_auth_header"


@pytest.mark.asyncio
async def test_unauthenticated_tool_call_is_rejected_before_invocation() -> None:
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.test") as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "get_incident", "arguments": {"incident_id": "11111111-1111-1111-1111-111111111111"}},
            },
            headers={"Accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 401
    assert response.json()["error"] == "missing_auth_header"


@pytest.mark.asyncio
async def test_malformed_bearer_header_is_rejected_with_401() -> None:
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.test") as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": "NotBearer something",
            },
        )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_auth_header_format"
