"""MCP Auth (mcpauth) configuration and per-tool scope enforcement.

The MCP server is protected with the `mcpauth` package's bearer-token
middleware (JWT mode), **not** FastMCP's own built-in OAuth provider. All
issuer/JWKS/audience settings are read from environment variables — nothing
is hardcoded here.

`mcpauth`'s ``bearer_auth_middleware`` verifies the token's signature, issuer
and (optionally) audience once per HTTP request and stores the resulting
`AuthInfo` in a `contextvars.ContextVar`. Because a single Streamable HTTP
endpoint multiplexes many MCP tools with *different* scope requirements,
per-tool scopes are enforced individually inside each tool via
`require_scope`, not globally in the middleware.

mcpauth 0.1.1 only implements OAuth 2.0 *Authorization Server* Metadata
(``/.well-known/oauth-authorization-server``, RFC 8414) — it has no support
for OAuth 2.0 *Protected Resource* Metadata (RFC 9728), which the MCP
Authorization spec also requires so clients can discover which authorization
server(s) protect this resource. That endpoint is implemented directly in
this module (``protected_resource_metadata_route``) rather than by patching
mcpauth or using FastMCP's built-in OAuth provider.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any
from urllib.parse import urlsplit

from mcpauth import MCPAuth
from mcpauth.config import AuthorizationServerMetadata, AuthServerConfig, AuthServerType
from mcpauth.types import AuthInfo
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from errors import AuthenticationFailedError, ScopeDeniedError

# Least-privilege scopes this MCP server's tools require (see incident_tools.py
# and inventory_tools.py). Advertised in Protected Resource Metadata so clients
# know what to request.
PROTECTED_RESOURCE_SCOPES = ["incidents:read", "incidents:create", "incidents:update", "inventory:read"]

PROTECTED_RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource"
AUTHORIZATION_SERVER_METADATA_PATH = "/.well-known/oauth-authorization-server"
PUBLIC_METADATA_PATHS = {
    PROTECTED_RESOURCE_METADATA_PATH,
    AUTHORIZATION_SERVER_METADATA_PATH,
}

# Context variable mcp-auth populates with the verified AuthInfo for the
# in-flight request. Exposed at module level so tests can set/clear it
# directly without reaching into MCPAuth internals.
AUTH_CONTEXT: ContextVar[AuthInfo | None] = ContextVar("trackflow_mcp_auth", default=None)


class AuthConfigError(RuntimeError):
    """Raised when required MCP Auth environment variables are missing."""


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise AuthConfigError(f"Missing required environment variable: {name}")
    return value


def build_auth_server_config() -> AuthServerConfig:
    """Build mcpauth's `AuthServerConfig` entirely from environment variables.

    Required:
      - MCP_AUTH_ISSUER
      - MCP_AUTH_AUTHORIZATION_ENDPOINT
      - MCP_AUTH_TOKEN_ENDPOINT
      - MCP_AUTH_JWKS_URI

    Optional:
      - MCP_AUTH_SERVER_TYPE ("oauth" or "oidc", default "oauth")
    """
    issuer = _require_env("MCP_AUTH_ISSUER")
    authorization_endpoint = _require_env("MCP_AUTH_AUTHORIZATION_ENDPOINT")
    token_endpoint = _require_env("MCP_AUTH_TOKEN_ENDPOINT")
    jwks_uri = _require_env("MCP_AUTH_JWKS_URI")
    server_type = os.environ.get("MCP_AUTH_SERVER_TYPE", "oauth").strip().lower()

    metadata = AuthorizationServerMetadata(
        issuer=issuer,
        authorization_endpoint=authorization_endpoint,
        token_endpoint=token_endpoint,
        jwks_uri=jwks_uri,
        response_types_supported=["code"],
        grant_types_supported=["authorization_code"],
        code_challenge_methods_supported=["S256"],
    )
    return AuthServerConfig(
        metadata=metadata,
        type=AuthServerType.OIDC if server_type == "oidc" else AuthServerType.OAUTH,
    )


def get_mcp_audience() -> str | None:
    """Optional expected `aud` claim, from MCP_AUTH_AUDIENCE."""
    return os.environ.get("MCP_AUTH_AUDIENCE") or None


_mcp_auth_instance: MCPAuth | None = None


def get_mcp_auth() -> MCPAuth:
    """Lazily built, process-wide `MCPAuth` instance."""
    global _mcp_auth_instance
    if _mcp_auth_instance is None:
        _mcp_auth_instance = MCPAuth(
            server=build_auth_server_config(),
            context_var=AUTH_CONTEXT,
        )
    return _mcp_auth_instance


def reset_mcp_auth_cache() -> None:
    """Test-only helper: force re-reading env vars on the next `get_mcp_auth()`."""
    global _mcp_auth_instance
    _mcp_auth_instance = None


def build_bearer_auth_middleware() -> Middleware:
    """Require mcpauth bearer auth for MCP requests, not public metadata."""
    mcp_auth = get_mcp_auth()
    base_bearer_middleware = mcp_auth.bearer_auth_middleware(
        "jwt",
        audience=get_mcp_audience(),
    )

    class SelectiveBearerMiddleware(base_bearer_middleware):
        async def dispatch(self, request: Request, call_next):
            if request.url.path in PUBLIC_METADATA_PATHS:
                return await call_next(request)
            return await super().dispatch(request, call_next)

    return Middleware(SelectiveBearerMiddleware)


def current_auth_info() -> AuthInfo:
    """Return the verified `AuthInfo` for the in-flight request, or raise.

    Raises `AuthenticationFailedError` when no authenticated context is
    present (the bearer-auth middleware rejects unauthenticated requests
    before they ever reach a tool, so this is mostly a defensive check for
    direct/in-process tool invocation).
    """
    auth_info = AUTH_CONTEXT.get()
    if auth_info is None:
        raise AuthenticationFailedError("No verified bearer token found for this request.")
    return auth_info


def require_scope(scope: str) -> AuthInfo:
    """Fetch the current `AuthInfo` and enforce a single required scope."""
    auth_info = current_auth_info()
    if scope not in (auth_info.scopes or []):
        raise ScopeDeniedError([scope])
    return auth_info


def get_resource_url() -> str:
    """Canonical resource URI for this MCP server (RFC 9728 `resource`).

    Defaults to the local host/port the server binds to. Production
    deployments behind a reverse proxy or a Codespaces-forwarded URL should
    set `MCP_RESOURCE_URL` explicitly so it matches the public-facing URL
    clients actually connect to.
    """
    configured = os.environ.get("MCP_RESOURCE_URL")
    if configured:
        return configured.rstrip("/")
    host = os.environ.get("MCP_SERVER_HOST", "127.0.0.1")
    port = os.environ.get("MCP_SERVER_PORT", "8800")
    return f"http://{host}:{port}/mcp"


def build_protected_resource_metadata() -> dict[str, Any]:
    """OAuth 2.0 Protected Resource Metadata (RFC 9728) for this MCP server."""
    return {
        "resource": get_resource_url(),
        "authorization_servers": [_require_env("MCP_AUTH_ISSUER")],
        "scopes_supported": list(PROTECTED_RESOURCE_SCOPES),
        "bearer_methods_supported": ["header"],
    }


def _cors_metadata_response(body: dict[str, Any] | None, *, status_code: int) -> Response:
    response: Response = Response(status_code=status_code) if body is None else JSONResponse(body, status_code=status_code)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


def protected_resource_metadata_route() -> Route:
    """Starlette route serving RFC 9728 Protected Resource Metadata.

    mcpauth 0.1.1 has no built-in support for this metadata type (it only
    implements Authorization Server Metadata), so it is served directly here.
    """

    async def endpoint(request: Request) -> Response:
        if request.method == "OPTIONS":
            return _cors_metadata_response(None, status_code=204)
        return _cors_metadata_response(build_protected_resource_metadata(), status_code=200)

    return Route(PROTECTED_RESOURCE_METADATA_PATH, endpoint, methods=["GET", "OPTIONS"])


def authorization_server_metadata_route() -> Route:
    """Mount mcpauth's own `/.well-known/oauth-authorization-server` route (RFC 8414)."""
    return get_mcp_auth().metadata_route()


class ResourceMetadataChallengeMiddleware(BaseHTTPMiddleware):
    """Adds a spec-correct `WWW-Authenticate` resource_metadata pointer to 401s.

    mcpauth's bearer-auth middleware returns a bare 401 with no
    `WWW-Authenticate` header, leaving clients no way to discover *where*
    the Protected Resource Metadata lives. This wraps the response rather
    than modifying mcpauth internals; must be listed before the bearer-auth
    middleware so it wraps outside it.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if response.status_code == 401:
            configured_url = os.environ.get("MCP_RESOURCE_URL")
            if configured_url:
                parsed = urlsplit(configured_url.rstrip("/"))
                metadata_origin = f"{parsed.scheme}://{parsed.netloc}"
            else:
                metadata_origin = str(request.base_url).rstrip("/")
            metadata_url = f"{metadata_origin}{PROTECTED_RESOURCE_METADATA_PATH}"
            response.headers["WWW-Authenticate"] = f'Bearer resource_metadata="{metadata_url}"'
        return response


def build_resource_metadata_challenge_middleware() -> Middleware:
    """Starlette `Middleware` entry for `ResourceMetadataChallengeMiddleware`."""
    return Middleware(ResourceMetadataChallengeMiddleware)
