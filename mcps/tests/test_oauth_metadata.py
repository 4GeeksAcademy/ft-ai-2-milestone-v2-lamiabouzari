"""OAuth metadata discovery tests (RFC 8414 + RFC 9728).

Exercises the real ASGI app so these prove what a client (including MCP
Playground) actually receives over HTTP, not just the Python helpers.
"""

from __future__ import annotations

import httpx
import pytest

import server
from auth import (
    PROTECTED_RESOURCE_METADATA_PATH,
    PROTECTED_RESOURCE_SCOPES,
    build_auth_server_config,
)


@pytest.mark.asyncio
async def test_protected_resource_metadata_endpoint_exists_and_is_well_formed() -> None:
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.test") as client:
        response = await client.get(PROTECTED_RESOURCE_METADATA_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["resource"]
    assert body["authorization_servers"] == ["https://auth.test.trackflow.example"]
    assert set(body["scopes_supported"]) == set(PROTECTED_RESOURCE_SCOPES)
    assert body["bearer_methods_supported"] == ["header"]


@pytest.mark.asyncio
async def test_authorization_server_metadata_endpoint_exposes_required_fields() -> None:
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.test") as client:
        response = await client.get("/.well-known/oauth-authorization-server")

    assert response.status_code == 200
    body = response.json()
    assert body["issuer"] == "https://auth.test.trackflow.example"
    assert body["authorization_endpoint"] == "https://auth.test.trackflow.example/authorize"
    assert body["token_endpoint"] == "https://auth.test.trackflow.example/token"
    assert body["jwks_uri"] == "https://auth.test.trackflow.example/jwks"
    assert "code" in body["response_types_supported"]
    assert body["grant_types_supported"] == ["authorization_code"]
    assert body["code_challenge_methods_supported"] == ["S256"]


def test_auth_server_config_has_required_oauth_endpoints_and_pkce() -> None:
    metadata = build_auth_server_config().metadata
    assert metadata.issuer == "https://auth.test.trackflow.example"
    assert metadata.authorization_endpoint == "https://auth.test.trackflow.example/authorize"
    assert metadata.token_endpoint == "https://auth.test.trackflow.example/token"
    assert metadata.jwks_uri == "https://auth.test.trackflow.example/jwks"
    assert "code" in metadata.response_types_supported
    assert "authorization_code" in metadata.grant_types_supported
    assert "S256" in metadata.code_challenge_methods_supported


@pytest.mark.asyncio
async def test_unauthenticated_401_points_to_protected_resource_metadata() -> None:
    """A 401 must carry a WWW-Authenticate challenge naming the metadata URL."""
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.test") as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 401
    challenge = response.headers["WWW-Authenticate"]
    assert "Bearer" in challenge
    assert f'resource_metadata="http://mcp.test{PROTECTED_RESOURCE_METADATA_PATH}"' in challenge


@pytest.mark.asyncio
async def test_configured_resource_url_is_used_in_unauthenticated_challenge(monkeypatch) -> None:
    monkeypatch.setenv("MCP_RESOURCE_URL", "https://public.example.com/mcp")
    app = server.create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://internal.test") as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == (
        'Bearer resource_metadata="https://public.example.com/.well-known/oauth-protected-resource"'
    )
