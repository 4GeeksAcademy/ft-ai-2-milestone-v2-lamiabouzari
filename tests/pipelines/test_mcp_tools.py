"""Unit tests for the LangGraph-side MCP client layer (`data/pipelines/mcp_tools.py`).

All tests mock `MultiServerMCPClient`/the returned LangChain tool — none of
them requires a live MCP server or OAuth provider.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from data.pipelines import mcp_tools


class _FakeTool:
    def __init__(self, name, handler):
        self.name = name
        self._handler = handler

    async def ainvoke(self, tool_call):
        return await self._handler(tool_call)


class _FakeClient:
    def __init__(self, tools=None, get_tools_error=None):
        self._tools = tools or []
        self._get_tools_error = get_tools_error

    async def get_tools(self, *, server_name=None):
        if self._get_tools_error is not None:
            raise self._get_tools_error
        return self._tools


def _tool_message(status, content, artifact=None):
    return SimpleNamespace(status=status, content=content, artifact=artifact)


def _use_client(monkeypatch, client: _FakeClient) -> None:
    monkeypatch.setattr(mcp_tools, "_build_client", lambda: client)


# -- connection configuration -------------------------------------------------


def test_connections_use_env_server_url_and_streamable_http_transport(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_URL", "https://mcp.example.com/mcp")
    monkeypatch.delenv("MCP_CLIENT_ACCESS_TOKEN", raising=False)

    config = mcp_tools._build_connections()["trackflow"]

    assert config["url"] == "https://mcp.example.com/mcp"
    assert config["transport"] == "streamable_http"
    assert config["headers"] == {}


def test_connections_default_server_url_when_env_not_set(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_URL", raising=False)

    config = mcp_tools._build_connections()["trackflow"]

    assert config["url"] == mcp_tools.DEFAULT_MCP_SERVER_URL


def test_connections_include_authorization_header_when_token_configured(monkeypatch):
    monkeypatch.setenv("MCP_CLIENT_ACCESS_TOKEN", "super-secret-token")

    config = mcp_tools._build_connections()["trackflow"]

    assert config["headers"] == {"Authorization": "Bearer super-secret-token"}


def test_connections_omit_authorization_header_when_token_not_configured(monkeypatch):
    monkeypatch.delenv("MCP_CLIENT_ACCESS_TOKEN", raising=False)

    config = mcp_tools._build_connections()["trackflow"]

    assert config["headers"] == {}


def test_token_never_appears_in_returned_failure_result(monkeypatch):
    monkeypatch.setenv("MCP_CLIENT_ACCESS_TOKEN", "super-secret-token")
    _use_client(monkeypatch, _FakeClient(get_tools_error=RuntimeError("boom")))

    result = mcp_tools.lookup_incident_via_mcp("11111111-1111-1111-1111-111111111111")

    assert "super-secret-token" not in str(result)
    assert result["found"] is False


def test_exception_message_contents_are_never_surfaced(monkeypatch):
    class _LeakyError(RuntimeError):
        pass

    error = _LeakyError("failed with Authorization: Bearer super-secret-token")
    _use_client(monkeypatch, _FakeClient(get_tools_error=error))

    result = mcp_tools.lookup_incident_via_mcp("abc")

    assert "super-secret-token" not in str(result)
    assert result["error"] == "error"


# -- tool selection and successful result normalization -----------------------


def test_selects_get_incident_tool_among_multiple(monkeypatch):
    seen_args = {}

    async def handle_get_incident(tool_call):
        seen_args["args"] = tool_call["args"]
        return _tool_message(
            "success",
            [{"type": "text", "text": "ok"}],
            artifact={
                "structured_content": {
                    "id": tool_call["args"]["incident_id"],
                    "status": "open",
                    "category": "damage",
                    "origin": "customer",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-02T00:00:00+00:00",
                }
            },
        )

    async def handle_other(_tool_call):
        raise AssertionError("wrong tool invoked")

    other_tool = _FakeTool("create_incident", handle_other)
    get_tool = _FakeTool("get_incident", handle_get_incident)
    _use_client(monkeypatch, _FakeClient(tools=[other_tool, get_tool]))

    result = mcp_tools.lookup_incident_via_mcp("abc-123")

    assert seen_args["args"] == {"incident_id": "abc-123"}
    assert result == {
        "found": True,
        "incident_id": "abc-123",
        "status": "open",
        "category": "damage",
        "origin": "customer",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-02T00:00:00+00:00",
        "error": None,
    }


def test_missing_get_incident_tool_is_mapped_to_error(monkeypatch):
    async def handle_other(_tool_call):
        raise AssertionError("no get_incident tool should be invoked")

    other_tool = _FakeTool("create_incident", handle_other)
    _use_client(monkeypatch, _FakeClient(tools=[other_tool]))

    result = mcp_tools.lookup_incident_via_mcp("abc")

    assert result["found"] is False
    assert result["error"] == "error"


# -- controlled failure outcomes ----------------------------------------------


def test_connection_failure_maps_to_unavailable(monkeypatch):
    _use_client(monkeypatch, _FakeClient(get_tools_error=httpx.ConnectError("refused")))

    result = mcp_tools.lookup_incident_via_mcp("abc")

    assert result == {
        "found": False,
        "incident_id": "abc",
        "status": None,
        "category": None,
        "origin": None,
        "created_at": None,
        "updated_at": None,
        "error": "unavailable",
    }


@pytest.mark.parametrize(
    ("error_text", "expected_outcome"),
    [
        ("NOT_FOUND: Resource not found: GET /api/incidents/x", "not_found"),
        ("BACKEND_TIMEOUT: TrackFlow backend timed out calling GET /api/incidents/x.", "timeout"),
        ("BACKEND_ERROR: TrackFlow backend error (500) calling GET /api/incidents/x.", "unavailable"),
        ("AUTHENTICATION_REQUIRED: No verified bearer token found for this request.", "authentication"),
        ("Insufficient scope. Required: incidents:read", "authorization"),
        ("Some unexpected failure", "error"),
    ],
)
def test_tool_error_outcomes_are_mapped(monkeypatch, error_text, expected_outcome):
    async def handle_get_incident(_tool_call):
        return _tool_message("error", [{"type": "text", "text": error_text}])

    tool = _FakeTool("get_incident", handle_get_incident)
    _use_client(monkeypatch, _FakeClient(tools=[tool]))

    result = mcp_tools.lookup_incident_via_mcp("abc")

    assert result["found"] is False
    assert result["error"] == expected_outcome
    assert result["status"] is None


def test_malformed_payload_without_artifact_is_mapped_to_error(monkeypatch):
    async def handle_get_incident(_tool_call):
        return _tool_message("success", [{"type": "text", "text": "ok"}], artifact=None)

    tool = _FakeTool("get_incident", handle_get_incident)
    _use_client(monkeypatch, _FakeClient(tools=[tool]))

    result = mcp_tools.lookup_incident_via_mcp("abc")

    assert result["found"] is False
    assert result["error"] == "error"


def test_malformed_payload_missing_fields_is_mapped_to_error(monkeypatch):
    async def handle_get_incident(_tool_call):
        return _tool_message(
            "success",
            [{"type": "text", "text": "ok"}],
            artifact={"structured_content": {"id": "abc"}},  # missing status/category/...
        )

    tool = _FakeTool("get_incident", handle_get_incident)
    _use_client(monkeypatch, _FakeClient(tools=[tool]))

    result = mcp_tools.lookup_incident_via_mcp("abc")

    assert result["found"] is False
    assert result["error"] == "error"
    # Never invent field values for a malformed payload.
    assert result["status"] is None
    assert result["category"] is None


def test_slow_tool_call_times_out(monkeypatch):
    async def handle_get_incident(_tool_call):
        await asyncio.sleep(0.5)
        return _tool_message("success", [{"type": "text", "text": "ok"}])

    tool = _FakeTool("get_incident", handle_get_incident)
    _use_client(monkeypatch, _FakeClient(tools=[tool]))

    result = mcp_tools.lookup_incident_via_mcp("abc", timeout=0.05)

    assert result["found"] is False
    assert result["error"] == "timeout"
