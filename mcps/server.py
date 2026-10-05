"""MCP server entry point.

Boots a FastMCP server over Streamable HTTP, protected end-to-end by MCP
Auth (`mcpauth`) bearer-token verification — explicitly *not* FastMCP's own
built-in OAuth provider. OAuth/OIDC settings and the TrackFlow backend URL
are all read from environment variables (see `.env.example`); nothing is
hardcoded.
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

import incident_tools
import inventory_tools
from auth import (
    authorization_server_metadata_route,
    build_bearer_auth_middleware,
    build_resource_metadata_challenge_middleware,
    protected_resource_metadata_route,
)

mcp = FastMCP(
    name="trackflow-mcp",
    instructions=(
        "TrackFlow MCP server. Provides read/create/update access to the Incident "
        "Manager API and strictly read-only access to Inventory. Every tool call "
        "requires an OAuth2 bearer token verified by MCP Auth (mcpauth) with the "
        "appropriate scope (incidents:read, incidents:create, incidents:update, "
        "inventory:read)."
    ),
    mask_error_details=True,
)

incident_tools.register(mcp)
inventory_tools.register(mcp)


def create_app():
    """Build the ASGI app: FastMCP Streamable HTTP + mcpauth bearer-auth middleware.

    Also mounts OAuth 2.0 Authorization Server Metadata
    (`/.well-known/oauth-authorization-server`, RFC 8414) and Protected
    Resource Metadata (`/.well-known/oauth-protected-resource`, RFC 9728) so
    clients (including MCP Playground) can discover the authorization
    server(s) and scopes protecting this resource.
    """
    app = mcp.http_app(
        transport="http",
        middleware=[
            # Outermost first: must see the bearer-auth middleware's 401s.
            build_resource_metadata_challenge_middleware(),
            build_bearer_auth_middleware(),
        ],
    )
    app.routes.append(authorization_server_metadata_route())
    app.routes.append(protected_resource_metadata_route())
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("MCP_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_SERVER_PORT", "8800"))
    uvicorn.run(app, host=host, port=port)
