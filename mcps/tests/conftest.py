"""Shared pytest fixtures for the mcps test suite.

Sets required MCP Auth / TrackFlow env vars *before* any application module
is imported (several modules read them at import or first-use time), adds
the `mcps/` package root to `sys.path` (it's a flat module layout, not an
installed package), and provides helpers for faking authenticated contexts
and mocking backend HTTP calls without any real network access.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

MCPS_ROOT = Path(__file__).resolve().parent.parent
if str(MCPS_ROOT) not in sys.path:
    sys.path.insert(0, str(MCPS_ROOT))

os.environ.setdefault("MCP_AUTH_ISSUER", "https://auth.test.trackflow.example")
os.environ.setdefault(
    "MCP_AUTH_AUTHORIZATION_ENDPOINT", "https://auth.test.trackflow.example/authorize"
)
os.environ.setdefault("MCP_AUTH_TOKEN_ENDPOINT", "https://auth.test.trackflow.example/token")
os.environ.setdefault("MCP_AUTH_JWKS_URI", "https://auth.test.trackflow.example/jwks")
os.environ.setdefault("MCP_AUTH_AUDIENCE", "trackflow-mcp")
os.environ.setdefault("TRACKFLOW_API_BASE_URL", "http://backend.test")

from collections.abc import Iterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402

import backend_client  # noqa: E402
from auth import AUTH_CONTEXT  # noqa: E402
from mcpauth.types import AuthInfo  # noqa: E402

TEST_ISSUER = os.environ["MCP_AUTH_ISSUER"]
TEST_SUBJECT = "user-123"


def make_auth_info(scopes: list[str], *, subject: str = TEST_SUBJECT) -> AuthInfo:
    """Build a fake verified `AuthInfo` as mcpauth would produce after JWT checks."""
    return AuthInfo(
        token="test-token",  # noqa: S106 - fixture value, not a real secret
        issuer=TEST_ISSUER,
        subject=subject,
        scopes=scopes,
        claims={"sub": subject},
    )


@pytest.fixture
def authenticated(request: pytest.FixtureRequest) -> Iterator[AuthInfo]:
    """Populate AUTH_CONTEXT with an AuthInfo granting `request.param` scopes."""
    scopes: list[str] = getattr(request, "param", [])
    auth_info = make_auth_info(scopes)
    token = AUTH_CONTEXT.set(auth_info)
    try:
        yield auth_info
    finally:
        AUTH_CONTEXT.reset(token)


@pytest.fixture
def unauthenticated() -> Iterator[None]:
    """Ensure AUTH_CONTEXT is empty (simulating no verified bearer token)."""
    token = AUTH_CONTEXT.set(None)
    try:
        yield
    finally:
        AUTH_CONTEXT.reset(token)


@pytest.fixture
def mock_backend(monkeypatch: pytest.MonkeyPatch):
    """Patch `backend_client._client` to use an `httpx.MockTransport`.

    Usage: `mock_backend(lambda request: httpx.Response(200, json={...}))`.
    """

    def _apply(handler) -> None:
        def _client() -> httpx.AsyncClient:
            return httpx.AsyncClient(
                base_url=backend_client.get_base_url(),
                timeout=backend_client.get_timeout_seconds(),
                transport=httpx.MockTransport(handler),
            )

        monkeypatch.setattr(backend_client, "_client", _client)

    return _apply
