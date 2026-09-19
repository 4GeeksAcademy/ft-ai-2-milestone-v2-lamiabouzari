"""Prefect pipeline for weekly warehouse/client performance reporting."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import text

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _REPO_ROOT / "services" / ".env"
if _ENV_FILE.exists():
    from dotenv import load_dotenv

    load_dotenv(_ENV_FILE)

_SERVICES_DIR = _REPO_ROOT / "services"
if str(_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICES_DIR))

from prefect import flow, get_run_logger, task
from prefect.cache_policies import INPUTS
from prefect.task_runners import ThreadPoolTaskRunner

from database import get_inventory_engine

REQUIRED_EVENT_TYPES = [
    "inbound_order_created",
    "outbound_order_created",
    "stock_threshold_triggered",
    "inventory_discrepancy_detected",
]


def _completed_week_start(week_start: date | None = None) -> date:
    """Return the requested week or the most recently completed UTC week."""
    if week_start is not None:
        return week_start
    today = datetime.now(UTC).date()
    current_monday = today - timedelta(days=today.weekday())
    return current_monday - timedelta(days=7)


def _utc_bounds(week_start: date) -> tuple[datetime, datetime]:
    start = datetime.combine(week_start, time.min, tzinfo=UTC)
    return start, start + timedelta(days=7)


def _tags_value(tags: Any, key: str, default: Any = None) -> Any:
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            return default
    return tags.get(key, default) if isinstance(tags, dict) else default


@task(retries=2, retry_delay_seconds=10)
def extract_weekly_events(week_start: date) -> list[dict[str, Any]]:
    """Read only the four business event types for one completed week."""
    start_utc, end_utc = _utc_bounds(week_start)
    query = text(
        """
        SELECT
            et.event_id,
            et.timestamp,
            et.event_type,
            et.tags
        FROM telemetry_events et
        WHERE et.event_type IN :event_types
          AND et.timestamp >= :start_utc
          AND et.timestamp < :end_utc
        ORDER BY et.timestamp
        """
    ).bindparams(sa.bindparam("event_types", expanding=True))

    with get_inventory_engine().connect() as connection:
        rows = connection.execute(
            query,
            {
                "event_types": REQUIRED_EVENT_TYPES,
                "start_utc": start_utc,
                "end_utc": end_utc,
            },
        ).mappings().all()
    return [dict(row) for row in rows]


@task(cache_policy=INPUTS, cache_expiration=timedelta(hours=1))
def transform_warehouse_client_kpis(
    events: list[dict[str, Any]], week_start: date
) -> list[dict[str, Any]]:
    """Aggregate source events by warehouse, client, and reporting week."""
    groups: dict[tuple[str, str, date], dict[str, Any]] = {}
    for event in events:
        tags = event.get("tags") or {}
        warehouse = _tags_value(tags, "warehouse")
        client_id = _tags_value(tags, "client_id")
        if not warehouse or not client_id:
            continue
        key = (str(warehouse), str(client_id), week_start)
        metrics = groups.setdefault(
            key,
            {
                "warehouse": str(warehouse),
                "client_id": str(client_id),
                "week_start": week_start,
                "inbound_units_count": 0,
                "outbound_orders_count": 0,
                "stockout_events_count": 0,
                "discrepancy_events_count": 0,
            },
        )
        event_type = event.get("event_type")
        if event_type == "inbound_order_created":
            metrics["inbound_units_count"] += int(_tags_value(tags, "quantity", 0) or 0)
        elif event_type == "outbound_order_created":
            metrics["outbound_orders_count"] += 1
        elif event_type == "stock_threshold_triggered":
            metrics["stockout_events_count"] += 1
        elif event_type == "inventory_discrepancy_detected":
            metrics["discrepancy_events_count"] += 1

    for metrics in groups.values():
        outbound = metrics["outbound_orders_count"]
        metrics["discrepancy_rate"] = (
            metrics["discrepancy_events_count"] / outbound if outbound else 0
        )
        metrics["week_end"] = week_start + timedelta(days=7)
    return list(groups.values())


@task(retries=2, retry_delay_seconds=10)
def load_weekly_performance(
    kpis: list[dict[str, Any]], run_id: str, triggered_by: str
) -> int:
    """Create reporting tables and UPSERT the transformed KPI rows."""
    engine = get_inventory_engine()
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS reporting"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS reporting.weekly_warehouse_client_performance (
                    warehouse TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    week_start DATE NOT NULL,
                    week_end DATE NOT NULL,
                    inbound_units_count INTEGER NOT NULL,
                    outbound_orders_count INTEGER NOT NULL,
                    stockout_events_count INTEGER NOT NULL,
                    discrepancy_events_count INTEGER NOT NULL,
                    discrepancy_rate DOUBLE PRECISION NOT NULL,
                    computed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (warehouse, client_id, week_start)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS reporting.pipeline_runs (
                    run_id UUID PRIMARY KEY,
                    started_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ,
                    records_processed INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_details TEXT,
                    week_start DATE NOT NULL,
                    week_end DATE NOT NULL,
                    triggered_by TEXT NOT NULL
                )
                """
            )
        )
        upsert = text(
            """
            INSERT INTO reporting.weekly_warehouse_client_performance
                (warehouse, client_id, week_start, week_end,
                 inbound_units_count, outbound_orders_count,
                 stockout_events_count, discrepancy_events_count,
                 discrepancy_rate, computed_at)
            VALUES
                (:warehouse, :client_id, :week_start, :week_end,
                 :inbound_units_count, :outbound_orders_count,
                 :stockout_events_count, :discrepancy_events_count,
                 :discrepancy_rate, CURRENT_TIMESTAMP)
            ON CONFLICT (warehouse, client_id, week_start) DO UPDATE SET
                week_end = EXCLUDED.week_end,
                inbound_units_count = EXCLUDED.inbound_units_count,
                outbound_orders_count = EXCLUDED.outbound_orders_count,
                stockout_events_count = EXCLUDED.stockout_events_count,
                discrepancy_events_count = EXCLUDED.discrepancy_events_count,
                discrepancy_rate = EXCLUDED.discrepancy_rate,
                computed_at = CURRENT_TIMESTAMP
            """
        )
        if kpis:
            connection.execute(upsert, kpis)
        connection.execute(
            text(
                """
                UPDATE reporting.pipeline_runs
                SET completed_at = CURRENT_TIMESTAMP,
                    records_processed = :records_processed,
                    status = 'Completed',
                    error_details = NULL
                WHERE run_id = :run_id
                """
            ),
            {"run_id": run_id, "records_processed": len(kpis)},
        )
    return len(kpis)

@flow(name="extract_weekly_events_flow")
def extract_weekly_events_flow(week_start: date) -> list[dict[str, Any]]:
    """Extract weekly telemetry events for the reporting period."""
    return extract_weekly_events(week_start)


@flow(name="transform_warehouse_client_kpis_flow")
def transform_warehouse_client_kpis_flow(
    events: list[dict[str, Any]], week_start: date
) -> list[dict[str, Any]]:
    """Transform weekly events into warehouse/client KPI rows."""
    return transform_warehouse_client_kpis(events, week_start)


@flow(name="load_weekly_performance_flow")
def load_weekly_performance_flow(
    kpis: list[dict[str, Any]], run_id: str, triggered_by: str
) -> int:
    """Load weekly KPI rows and complete the pipeline run."""
    return load_weekly_performance(kpis, run_id, triggered_by)


@task

def export_audit_snapshot(kpis: list[dict[str, Any]], run_id: str) -> str:
    """Return a compact audit snapshot for optional downstream export."""
    return json.dumps({"run_id": run_id, "records": kpis}, default=str)


def _create_run(run_id: str, week_start: date, triggered_by: str) -> None:
    week_end = week_start + timedelta(days=7)
    with get_inventory_engine().begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS reporting"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS reporting.pipeline_runs (
                    run_id UUID PRIMARY KEY, started_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ, records_processed INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL, error_details TEXT, week_start DATE NOT NULL,
                    week_end DATE NOT NULL, triggered_by TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO reporting.pipeline_runs
                    (run_id, started_at, status, week_start, week_end, triggered_by)
                VALUES (:run_id, CURRENT_TIMESTAMP, 'Running', :week_start, :week_end, :triggered_by)
                """
            ),
            {"run_id": run_id, "week_start": week_start, "week_end": week_end, "triggered_by": triggered_by},
        )


def _fail_run(run_id: str, error: Exception) -> None:
    with get_inventory_engine().begin() as connection:
        connection.execute(
            text(
                """
                UPDATE reporting.pipeline_runs
                SET completed_at = CURRENT_TIMESTAMP, status = 'Failed', error_details = :error_details
                WHERE run_id = :run_id
                """
            ),
            {"run_id": run_id, "error_details": str(error)},
        )


@flow(name="weekly_warehouse_client_performance_pipeline", task_runner=ThreadPoolTaskRunner())
def weekly_warehouse_client_performance_pipeline(
    week_start: date | None = None,
    triggered_by: str = "scheduled",
    export_audit: bool = True,
    run_id: str | None = None,
) -> int:
    """Extract, transform, and load weekly warehouse/client performance KPIs."""
    logger = get_run_logger()
    resolved_week = _completed_week_start(week_start)
    run_id = run_id or str(uuid.uuid4())
    _create_run(run_id, resolved_week, triggered_by)
    try:
        events = extract_weekly_events_flow(resolved_week)
        kpis = transform_warehouse_client_kpis_flow(events, resolved_week)
        processed = load_weekly_performance_flow(kpis, run_id, triggered_by)
        if export_audit:
            audit_state = export_audit_snapshot(kpis, run_id, return_state=True)
            if audit_state.is_failed():
                logger.warning("Audit snapshot failed: %s", audit_state.message)
        return processed
    except Exception as error:
        _fail_run(run_id, error)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the weekly performance pipeline")
    parser.add_argument("--week-start", type=date.fromisoformat, help="Monday in YYYY-MM-DD format")
    parser.add_argument("--triggered-by", default="cli", help="Run trigger identifier")
    args = parser.parse_args()
    weekly_warehouse_client_performance_pipeline(
        week_start=args.week_start, triggered_by=args.triggered_by
    )


if __name__ == "__main__":
    main()
