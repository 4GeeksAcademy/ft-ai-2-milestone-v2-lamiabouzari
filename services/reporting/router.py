"""Business reporting endpoints backed by the pipeline destination tables."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from database import get_inventory_engine
from dependencies import get_current_user
from models.user import UserPublic

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PIPELINES_DIR = _REPO_ROOT / "data" / "pipelines"
if str(_PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINES_DIR))

from tasks.pipeline_tasks import run_weekly_warehouse_client_performance

router = APIRouter(prefix="/reporting", tags=["reporting"])

_MISSING_RELATION_STATES = {"42P01", "3F000"}


def _missing_report_relation(error: ProgrammingError) -> bool:
    """True when the reporting schema or destination table has not been created yet."""
    sqlstate = getattr(error.orig, "sqlstate", None)
    return sqlstate in _MISSING_RELATION_STATES


_SOURCE_EVENT_TYPES = (
    "inbound_order_created",
    "outbound_order_created",
    "stock_threshold_triggered",
    "inventory_discrepancy_detected",
)


def _read_rows(statement: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]] | None:
    """Run one read. None means the reporting relation has not been created."""
    try:
        with get_inventory_engine().connect() as connection:
            return [dict(row) for row in connection.execute(text(statement), params or {}).mappings().all()]
    except ProgrammingError as error:
        if _missing_report_relation(error):
            return None
        raise


def _latest_pipeline_run() -> dict[str, Any] | None:
    rows = _read_rows(
        """
        SELECT run_id, started_at, completed_at, records_processed,
               status, error_details, week_start, week_end, triggered_by
        FROM reporting.pipeline_runs
        ORDER BY started_at DESC
        LIMIT 1
        """
    )
    if not rows:
        return None
    return rows[0]


def _source_gap(week_start: date, week_end: date) -> dict[str, int]:
    """Count source events the completed run could not turn into KPI rows."""
    start = datetime.combine(week_start, time.min, tzinfo=UTC)
    end = datetime.combine(week_end, time.min, tzinfo=UTC)
    rows = _read_rows(
        """
        SELECT
            COUNT(*) AS source_events,
            COUNT(*) FILTER (
                WHERE COALESCE(tags->>'client_id', '') = ''
            ) AS missing_client_id,
            COUNT(*) FILTER (
                WHERE COALESCE(tags->>'warehouse', '') = ''
            ) AS missing_warehouse
        FROM telemetry_events
        WHERE event_type = ANY(:event_types)
          AND timestamp >= :start_utc
          AND timestamp < :end_utc
        """,
        {
            "event_types": list(_SOURCE_EVENT_TYPES),
            "start_utc": start,
            "end_utc": end,
        },
    )
    if not rows:
        return {"source_events": 0, "missing_client_id": 0, "missing_warehouse": 0}
    gap = rows[0]
    return {
        "source_events": int(gap["source_events"]),
        "missing_client_id": int(gap["missing_client_id"]),
        "missing_warehouse": int(gap["missing_warehouse"]),
    }


def _empty_report(run: dict[str, Any] | None) -> dict[str, Any]:
    """Separate a pipeline that never ran from one that completed with no valid rows."""
    if run is None or run.get("status") != "Completed" or int(run.get("records_processed") or 0) != 0:
        return {"week_start": None, "entries": [], "report_state": "never_run"}
    return {
        "week_start": run["week_start"],
        "entries": [],
        "report_state": "completed_without_rows",
        "pipeline_run": {
            "status": run["status"],
            "records_processed": int(run["records_processed"]),
            "week_start": run["week_start"],
            "week_end": run["week_end"],
        },
        "source_gap": _source_gap(run["week_start"], run["week_end"]),
    }


@router.get("/weekly-warehouse-client-performance")
def weekly_warehouse_client_performance(
    week_start: date | None = Query(default=None),
    _user: UserPublic = Depends(get_current_user),
) -> dict[str, Any]:
    """Return all KPI rows for the requested or latest computed week."""
    if week_start is None:
        week_rows = _read_rows(
            """
            SELECT MAX(week_start) AS week_start
            FROM reporting.weekly_warehouse_client_performance
            """
        )
        if not week_rows or week_rows[0]["week_start"] is None:
            return _empty_report(_latest_pipeline_run())
        week_start = week_rows[0]["week_start"]

    rows = _read_rows(
        """
        SELECT warehouse, client_id, week_start, week_end,
               inbound_units_count, outbound_orders_count,
               stockout_events_count, discrepancy_events_count,
               discrepancy_rate, computed_at
        FROM reporting.weekly_warehouse_client_performance
        WHERE week_start = :week_start
        ORDER BY warehouse, client_id
        """,
        {"week_start": week_start},
    )
    if rows is None:
        return _empty_report(_latest_pipeline_run())
    if not rows:
        return _empty_report(_latest_pipeline_run())
    return {"week_start": week_start, "entries": rows, "report_state": "ready"}


@router.get("/pipeline-runs/latest")
def latest_pipeline_run(_user: UserPublic = Depends(get_current_user)) -> dict[str, Any]:
    """Return the most recently started pipeline run."""
    with get_inventory_engine().connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT run_id, started_at, completed_at, records_processed,
                       status, error_details, week_start, week_end, triggered_by
                FROM reporting.pipeline_runs
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
        ).mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pipeline runs found")
    return dict(row)


@router.post("/pipeline-runs", status_code=status.HTTP_202_ACCEPTED)
def trigger_pipeline(
    week_start: date | None = Query(default=None),
    _user: UserPublic = Depends(get_current_user),
) -> dict[str, Any]:
    """Queue the weekly performance pipeline on the independent worker."""
    task = run_weekly_warehouse_client_performance.apply_async(
        args=[week_start.isoformat() if week_start else None]
    )
    return {"task_id": task.id}
