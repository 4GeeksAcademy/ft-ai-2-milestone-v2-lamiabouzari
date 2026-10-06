"""LangGraph-side MCP client layer for the TrackFlow Incident Manager.

The support agent never calls the Incident Manager/TinyDB directly. Instead
it goes through this module, which talks to the `mcps/` MCP server over
Streamable HTTP using `langchain-mcp-adapters`:

    services (LangGraph agent)
        -> langchain-mcp-adapters (this module)
        -> Streamable HTTP + "Authorization: Bearer <token>"
        -> mcps/ MCP server (FastMCP + mcpauth)
        -> TrackFlow backend

Connection settings (`MCP_SERVER_URL`, `MCP_CLIENT_ACCESS_TOKEN`) are read
from the environment. The access token is never logged or included in any
raised error message.

Does not construct JSON-RPC manually and does not call TrackFlow HTTP
endpoints directly — every call goes through a `MultiServerMCPClient`
LangChain tool.
"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any
from uuid import uuid4

import httpx
from langchain_mcp_adapters.client import MultiServerMCPClient

DEFAULT_MCP_SERVER_URL = "http://localhost:8800/mcp"
DEFAULT_MCP_TIMEOUT_SECONDS = 10.0
_TRACKFLOW_SERVER = "trackflow"
_GET_INCIDENT_TOOL = "get_incident"


def _build_connections() -> dict[str, dict[str, Any]]:
    """Streamable HTTP connection config, bearer token from the environment."""
    token = os.environ.get("MCP_CLIENT_ACCESS_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return {
        _TRACKFLOW_SERVER: {
            "transport": "streamable_http",
            "url": os.environ.get("MCP_SERVER_URL", DEFAULT_MCP_SERVER_URL),
            "headers": headers,
            "timeout": DEFAULT_MCP_TIMEOUT_SECONDS,
        }
    }


def _build_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(_build_connections())


def _failure_result(incident_id: str | None, outcome: str) -> dict[str, Any]:
    """A controlled, honest failure outcome — never invents incident fields."""
    return {
        "found": False,
        "incident_id": incident_id,
        "status": None,
        "category": None,
        "origin": None,
        "created_at": None,
        "updated_at": None,
        "error": outcome,
    }


def _normalize_success(structured: dict[str, Any]) -> dict[str, Any]:
    """Map the real `get_incident` schema onto the agent's incident_result shape."""
    try:
        return {
            "found": True,
            "incident_id": structured["id"],
            "status": structured["status"],
            "category": structured["category"],
            "origin": structured["origin"],
            "created_at": structured["created_at"],
            "updated_at": structured["updated_at"],
            "error": None,
        }
    except (KeyError, TypeError):
        return _failure_result(None, "error")


def _content_text(content: Any) -> str:
    """Join the text blocks of a LangChain tool-message content payload."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(parts)
    return str(content)


def _outcome_from_tool_error_text(text: str) -> str:
    """Map a server-side coded error message (see `mcps/errors.py`) to an outcome."""
    lowered = text.lower()
    if "not_found" in lowered:
        return "not_found"
    if "authentication_required" in lowered:
        return "authentication"
    if "insufficient scope" in lowered:
        return "authorization"
    if "backend_timeout" in lowered:
        return "timeout"
    if "backend_error" in lowered:
        return "unavailable"
    return "error"


def _outcome_from_exception(exc: BaseException) -> str:
    """Map transport/network-level failures (no server response reached) to an outcome."""
    if isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.PoolTimeout, TimeoutError)):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 401:
            return "authentication"
        if status == 403:
            return "authorization"
        if status == 404:
            return "not_found"
        return "unavailable"
    if isinstance(exc, (httpx.ConnectError, httpx.NetworkError, ConnectionError, OSError)):
        return "unavailable"
    return "error"


def _extract_structured_content(message: Any) -> dict[str, Any] | None:
    artifact = getattr(message, "artifact", None)
    if isinstance(artifact, dict):
        structured = artifact.get("structured_content")
        if isinstance(structured, dict):
            return structured
    return None


async def _invoke_get_incident(incident_id: str) -> dict[str, Any]:
    client = _build_client()

    try:
        tools = await client.get_tools(server_name=_TRACKFLOW_SERVER)
    except Exception as exc:  # noqa: BLE001 - translated into a controlled outcome below
        return _failure_result(incident_id, _outcome_from_exception(exc))

    tool = next((candidate for candidate in tools if candidate.name == _GET_INCIDENT_TOOL), None)
    if tool is None:
        return _failure_result(incident_id, "error")

    tool_call = {
        "name": tool.name,
        "args": {"incident_id": incident_id},
        "id": str(uuid4()),
        "type": "tool_call",
    }
    try:
        message = await tool.ainvoke(tool_call)
    except Exception as exc:  # noqa: BLE001 - translated into a controlled outcome below
        return _failure_result(incident_id, _outcome_from_exception(exc))

    if getattr(message, "status", "success") == "error":
        return _failure_result(incident_id, _outcome_from_tool_error_text(_content_text(message.content)))

    structured = _extract_structured_content(message)
    if structured is None:
        return _failure_result(incident_id, "error")
    return _normalize_success(structured)


def lookup_incident_via_mcp(
    incident_id: str,
    *,
    timeout: float = DEFAULT_MCP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch one incident through the MCP `get_incident` tool.

    Runs the async MCP client call in a dedicated thread with its own event
    loop, so this is safe to call from either a sync or an already-running
    async context (never calls `asyncio.run()` on the caller's loop).
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, _invoke_get_incident(incident_id))
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            return _failure_result(incident_id, "timeout")
        except Exception as exc:  # noqa: BLE001 - translated into a controlled outcome below
            return _failure_result(incident_id, _outcome_from_exception(exc))


def authorize_order_access(
    order_id: str,
    *,
    subject: str | None,
    owned_order_ids: frozenset[str] | set[str] | tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """Decide whether an authenticated subject may read one order.

    Uses the same outcome names as MCP tool failures in this module
    (``authentication`` and ``authorization``). A subject who does not own
    the order is denied with ``authorization``, never ``not_found``, and the
    decision carries no order payload. ``order_id`` is compared to the
    session allow-list and is not echoed on denial.
    """
    requested = str(order_id)
    if subject is None or not str(subject).strip():
        return {"authorized": False, "error": "authentication"}
    owned = {str(item) for item in owned_order_ids}
    if requested not in owned:
        return {"authorized": False, "error": "authorization"}
    return {"authorized": True, "error": None}
