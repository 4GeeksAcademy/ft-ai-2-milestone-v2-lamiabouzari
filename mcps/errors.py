"""Structured MCP tool error types.

Each category subclasses one of FastMCP's own error bases so a) the message
survives FastMCP's error-masking logic untouched (see
``FastMCP._mask_error_details`` — ``FastMCPError`` subclasses are always
re-raised as-is) and b) we still get distinct Python types to raise/catch/log
by category server-side.

The wire protocol (JSON-RPC) only preserves the error message text, not the
Python exception class, so every category also prefixes a stable
machine-readable code onto its message (e.g. ``"NOT_FOUND: ..."``) — this is
what lets MCP clients and log consumers tell categories apart without a
generic "error" for everything.
"""

from __future__ import annotations

from fastmcp.exceptions import (
    AuthorizationError,
    InsufficientScopeError,
    ToolError,
    ValidationError,
)


class _CodedError:
    """Mixin that prefixes ``self.code`` onto the exception message."""

    code: str = "ERROR"

    def __init__(self, message: str, *args: object, **kwargs: object) -> None:
        super().__init__(f"{self.code}: {message}", *args, **kwargs)  # type: ignore[call-arg]


class AuthenticationFailedError(_CodedError, AuthorizationError):
    """No valid authenticated bearer-token context for this tool call."""

    code = "AUTHENTICATION_REQUIRED"


class ScopeDeniedError(InsufficientScopeError):
    """Caller is authenticated but lacks a required OAuth scope.

    Message formatting (``"Insufficient scope. Required: ..."``) is already
    distinct and comes from FastMCP's own ``InsufficientScopeError``.
    """


class RequestValidationFailedError(_CodedError, ValidationError):
    """Tool arguments failed validation before (or when) reaching the backend."""

    code = "VALIDATION_ERROR"


class ResourceNotFoundError(_CodedError, ToolError):
    """The requested resource does not exist in the TrackFlow backend.

    Note: deliberately subclasses `ToolError`, not FastMCP's own
    `NotFoundError` — the latter doesn't inherit from `FastMCPError`, so its
    message gets masked into a generic "Error calling tool ..." string
    whenever `mask_error_details=True` (as this server sets). `ToolError`
    messages are always preserved verbatim.
    """

    code = "NOT_FOUND"


class BackendServiceError(_CodedError, ToolError):
    """The TrackFlow backend returned an unexpected/error response."""

    code = "BACKEND_ERROR"


class BackendTimeoutError(_CodedError, ToolError):
    """The TrackFlow backend did not respond within the configured timeout."""

    code = "BACKEND_TIMEOUT"


class InventoryReadOnlyError(_CodedError, AuthorizationError):
    """Inventory modification was attempted through MCP; writes are prohibited."""

    code = "INVENTORY_READ_ONLY"
