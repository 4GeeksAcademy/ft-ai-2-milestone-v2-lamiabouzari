"""Telemetry analysis: technical/operational metrics from telemetry events.

Every metric follows the same pipeline:
1. SQL load (filtered subset of telemetry_events)
2. Pandas refine (extract nested JSONB fields)
3. Convert timestamps (utc=True)
4. Group by relevant dimensions
5. Aggregate with count / mean / sum
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from models.telemetry import TelemetryEventRecord

# ---------------------------------------------------------------------------
# In-memory cache with configurable TTL (default 60 seconds)
# ---------------------------------------------------------------------------


class _ReportCache:
    """Simple in-memory cache keyed by the resolved (start, end) window."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[float, dict[str, Any]]] = {}

    @staticmethod
    def _key(start: datetime, end: datetime) -> str:
        return f"{start.isoformat()}/{end.isoformat()}"

    def get(self, start: datetime, end: datetime) -> dict[str, Any] | None:
        """Return cached metrics if still fresh, otherwise None."""
        key = self._key(start, end)
        entry = self._data.get(key)
        if entry is None:
            return None
        stored_at, result = entry
        if time.monotonic() - stored_at > self._ttl:
            del self._data[key]
            return None
        return result

    def set(self, start: datetime, end: datetime, result: dict[str, Any]) -> None:
        """Store a result under the given date window."""
        key = self._key(start, end)
        self._data[key] = (time.monotonic(), result)

    def clear(self) -> None:
        self._data.clear()


# Module-level singleton — survives between requests
_cache = _ReportCache()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_events(
    session: Session,
    event_types: list[str],
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Load a filtered subset of telemetry rows into a DataFrame.

    Only the columns needed for analysis are fetched.  The date window is
    applied server-side so no unnecessary rows cross the wire.
    """
    stmt = (
        select(
            TelemetryEventRecord.timestamp,
            TelemetryEventRecord.event_type,
            TelemetryEventRecord.tags,
        )
        .where(TelemetryEventRecord.event_type.in_(event_types))
        .where(TelemetryEventRecord.timestamp >= start)
        .where(TelemetryEventRecord.timestamp < end)
        .order_by(TelemetryEventRecord.timestamp)
    )
    rows = session.exec(stmt).all()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        {
            "timestamp": [r.timestamp for r in rows],
            "event_type": [r.event_type for r in rows],
            "tags": [r.tags for r in rows],
        }
    )
    # Convert to timezone-aware UTC before any temporal grouping
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to a JSON-serialisable list of dicts.

    NumPy numeric types are coerced to native Python types so that FastAPI
    can serialise them without a custom encoder.
    """
    if df.empty:
        return []
    records = df.to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            if isinstance(value, (np.integer,)):
                record[key] = int(value)
            elif isinstance(value, (np.floating,)):
                # Keep None/NaN as None so the JSON output stays clean
                if np.isnan(value):
                    record[key] = None
                else:
                    record[key] = float(value)
    return records


def _tag(df: pd.DataFrame, col: str) -> pd.Series:
    """Safely extract a nested field from the JSONB ``tags`` column."""
    return df["tags"].apply(lambda t: t.get(col) if isinstance(t, dict) else None)


# ---------------------------------------------------------------------------
# Metric 1 — API failures by endpoint, HTTP status, and error code
# ---------------------------------------------------------------------------


def api_failures_by_endpoint(
    session: Session,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Count of ``api_request_failed`` events grouped by endpoint / status / error.

    Engineering question answered: *Which API routes are failing most often,
    at what HTTP status, and with which error code?*
    """
    df = _load_events(session, ["api_request_failed"], start, end)
    if df.empty:
        return []

    df["endpoint"] = _tag(df, "endpoint")
    df["http_status"] = _tag(df, "http_status")
    df["error_code"] = _tag(df, "error_code")

    grouped = (
        df.groupby(["endpoint", "http_status", "error_code"], dropna=False)
        .agg(count=("event_type", "count"))
        .reset_index()
    )
    return _records(grouped)


# ---------------------------------------------------------------------------
# Metric 2 — Auth / security signals
# ---------------------------------------------------------------------------


def auth_security_signals(
    session: Session,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Count of ``user_login_failed`` and ``permission_denied`` events.

    Engineering questions answered:
    - *Which auth methods and failure reasons are most common in login failures?*
    - *Which resource types and actions trigger the most permission denials?*
    """
    df = _load_events(
        session, ["user_login_failed", "permission_denied"], start, end
    )
    if df.empty:
        return []

    # --- user_login_failed -------------------------------------------------
    login = df[df["event_type"] == "user_login_failed"].copy()
    login_parts: list[pd.DataFrame] = []
    if not login.empty:
        login["auth_method"] = _tag(login, "auth_method")
        login["failure_reason"] = _tag(login, "failure_reason")
        login_parts.append(
            (
                login.groupby(["auth_method", "failure_reason"], dropna=False)
                .agg(count=("event_type", "count"))
                .reset_index()
                .assign(event_type="user_login_failed")
            )
        )

    # --- permission_denied --------------------------------------------------
    perm = df[df["event_type"] == "permission_denied"].copy()
    if not perm.empty:
        perm["resource_type"] = _tag(perm, "resource_type")
        perm["action"] = _tag(perm, "action")
        login_parts.append(
            (
                perm.groupby(["resource_type", "action"], dropna=False)
                .agg(count=("event_type", "count"))
                .reset_index()
                .assign(event_type="permission_denied")
            )
        )

    if not login_parts:
        return []

    result = pd.concat(login_parts, ignore_index=True)
    return _records(result)


# ---------------------------------------------------------------------------
# Metric 3 — Frontend performance (page-load latency & search metrics)
# ---------------------------------------------------------------------------


def frontend_performance(
    session: Session,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Page-load and search-query performance metrics.

    Engineering questions answered:
    - *Which screens have the highest average load time?*
    - *How does search volume and latency vary by search context?*
    """
    df = _load_events(
        session, ["page_load_measured", "search_query_executed"], start, end
    )
    if df.empty:
        return []

    parts: list[pd.DataFrame] = []

    # --- page_load_measured -------------------------------------------------
    page = df[df["event_type"] == "page_load_measured"].copy()
    if not page.empty:
        page["page_name"] = _tag(page, "page_name")
        page["duration_ms"] = pd.to_numeric(_tag(page, "duration_ms"), errors="coerce")
        parts.append(
            (
                page.groupby("page_name", dropna=False)
                .agg(
                    count=("event_type", "count"),
                    avg_duration_ms=("duration_ms", "mean"),
                )
                .reset_index()
                .assign(event_type="page_load_measured")
            )
        )

    # --- search_query_executed ----------------------------------------------
    search = df[df["event_type"] == "search_query_executed"].copy()
    if not search.empty:
        search["search_context"] = _tag(search, "search_context")
        search["duration_ms"] = pd.to_numeric(
            _tag(search, "duration_ms"), errors="coerce"
        )
        search["result_count"] = pd.to_numeric(
            _tag(search, "result_count"), errors="coerce"
        )
        parts.append(
            (
                search.groupby("search_context", dropna=False)
                .agg(
                    count=("event_type", "count"),
                    avg_result_count=("result_count", "mean"),
                    avg_duration_ms=("duration_ms", "mean"),
                )
                .reset_index()
                .assign(event_type="search_query_executed")
            )
        )

    if not parts:
        return []

    result = pd.concat(parts, ignore_index=True)
    return _records(result)


# ---------------------------------------------------------------------------
# Coordinator — resolve the window once, run all metrics, cache the result
# ---------------------------------------------------------------------------


def generate_report(
    session: Session,
    start_date: datetime,
    end_date: datetime,
) -> dict[str, Any]:
    """Run all three telemetry metrics for the given window.

    Results are cached in-memory for 60 seconds.  Consecutive requests with
    the same (start, end) window will return the cached result without
    hitting the database.
    """
    cached = _cache.get(start_date, end_date)
    if cached is not None:
        return cached

    report = {
        "api_failures_by_endpoint": api_failures_by_endpoint(
            session, start_date, end_date
        ),
        "auth_security_signals": auth_security_signals(
            session, start_date, end_date
        ),
        "frontend_performance": frontend_performance(
            session, start_date, end_date
        ),
    }

    _cache.set(start_date, end_date, report)
    return report