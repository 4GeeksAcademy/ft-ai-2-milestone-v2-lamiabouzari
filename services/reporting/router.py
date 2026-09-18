"""Business reporting endpoints backed by the pipeline destination tables."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import text

from database import get_inventory_engine

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PIPELINES_DIR = _REPO_ROOT / "data" / "pipelines"
if str(_PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINES_DIR))

from pipeline import weekly_warehouse_client_performance_pipeline

router = APIRouter(prefix="/reporting", tags=["reporting"])


@router.get("/weekly-warehouse-client-performance")
def weekly_warehouse_client_performance(
    week_start: date | None = Query(default=None),
) -> dict[str, Any]:
    """Return all KPI rows for the requested or latest computed week."""
    with get_inventory_engine().connect() as connection:
        if week_start is None:
            week_row = connection.execute(
                text(
                    """
                    SELECT MAX(week_start) AS week_start
                    FROM reporting.weekly_warehouse_client_performance
                    """
                )
            ).mappings().one()
            week_start = week_row["week_start"]
        if week_start is None:
            return {"week_start": None, "entries": []}

        rows = connection.execute(
            text(
                """
                SELECT warehouse, client_id, week_start, week_end,
                       inbound_units_count, outbound_orders_count,
                       stockout_events_count, discrepancy_events_count,
                       discrepancy_rate, computed_at
                FROM reporting.weekly_warehouse_client_performance
                WHERE week_start = :week_start
                ORDER BY warehouse, client_id
                """
            ),
            {"week_start": week_start},
        ).mappings().all()
    return {"week_start": week_start, "entries": [dict(row) for row in rows]}


@router.get("/pipeline-runs/latest")
def latest_pipeline_run() -> dict[str, Any]:
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
    background_tasks: BackgroundTasks,
    week_start: date | None = Query(default=None),
) -> dict[str, Any]:
    """Trigger the weekly performance Prefect flow through the application API."""
    run_id = str(uuid.uuid4())
    background_tasks.add_task(
        weekly_warehouse_client_performance_pipeline,
        week_start=week_start,
        triggered_by="api",
        run_id=run_id,
    )
    return {"run_id": run_id, "status": "Running"}
