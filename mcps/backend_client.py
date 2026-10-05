"""Shared HTTP client for talking to the real TrackFlow backend (`services/`).

MCP tools never duplicate business logic or storage — they call the existing
FastAPI endpoints under `services/routers/incidents.py` and
`services/routers/inventory.py` over HTTP, using a configurable base URL.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from errors import (
    BackendServiceError,
    BackendTimeoutError,
    RequestValidationFailedError,
    ResourceNotFoundError,
)

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT_SECONDS = 10.0


def get_base_url() -> str:
    """TrackFlow backend base URL, from TRACKFLOW_API_BASE_URL."""
    return os.environ.get("TRACKFLOW_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def get_timeout_seconds() -> float:
    """Request timeout (seconds), from TRACKFLOW_API_TIMEOUT_SECONDS."""
    try:
        return float(os.environ.get("TRACKFLOW_API_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _client() -> httpx.AsyncClient:
    """Build the httpx client used for backend calls.

    Factored out so tests can monkeypatch it to inject a `MockTransport`
    without touching real network/sockets.
    """
    return httpx.AsyncClient(base_url=get_base_url(), timeout=get_timeout_seconds())


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict):
        return str(body.get("detail") or body.get("message") or body)
    return str(body)


async def request_json(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Call the TrackFlow backend and translate HTTP/network failures.

    Raises `BackendTimeoutError`, `BackendServiceError`,
    `ResourceNotFoundError`, or `RequestValidationFailedError` as
    appropriate; returns the parsed JSON body (or `None` for empty
    responses) on success.
    """
    try:
        async with _client() as client:
            response = await client.request(method, path, json=json, params=params)
    except httpx.TimeoutException as exc:
        raise BackendTimeoutError(
            f"TrackFlow backend timed out calling {method} {path}."
        ) from exc
    except httpx.HTTPError as exc:
        raise BackendServiceError(
            f"TrackFlow backend request failed for {method} {path}: {exc}"
        ) from exc

    if response.status_code == 404:
        raise ResourceNotFoundError(f"Resource not found: {method} {path}")
    if response.status_code in (400, 422):
        raise RequestValidationFailedError(
            f"TrackFlow backend rejected the request: {_error_detail(response)}"
        )
    if response.status_code >= 500:
        raise BackendServiceError(
            f"TrackFlow backend error ({response.status_code}) calling {method} {path}."
        )
    if response.status_code >= 400:
        raise BackendServiceError(
            f"TrackFlow backend returned {response.status_code}: {_error_detail(response)}"
        )

    if response.status_code == 204 or not response.content:
        return None
    return response.json()
