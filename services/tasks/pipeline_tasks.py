"""Celery tasks that delegate to existing reporting pipelines."""

from __future__ import annotations

import logging
import sys
import time
from datetime import date
from pathlib import Path

from celery_app import celery_app
from dlq import record_dlq_entry

_LOGGER = logging.getLogger(__name__)
_PIPELINES_DIR = Path(__file__).resolve().parents[2] / "data" / "pipelines"
if str(_PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINES_DIR))


def retry_countdown(retries: int) -> int:
    """Return the exponential delay before the next Celery retry."""
    return 10 * (2**retries)


@celery_app.task(
    bind=True,
    name="tasks.weekly_warehouse_client_performance",
    max_retries=3,
    track_started=True,
)
def run_weekly_warehouse_client_performance(self, week_start: str | None = None) -> int:
    """Run the existing Prefect pipeline with Celery retry/DLQ handling."""
    started = time.monotonic()
    attempt = self.request.retries + 1
    task_id = self.request.id
    try:
        resolved_week = date.fromisoformat(week_start) if week_start else None
        from pipeline import weekly_warehouse_client_performance_pipeline

        result = weekly_warehouse_client_performance_pipeline(
            week_start=resolved_week,
            triggered_by="api",
        )
        _LOGGER.info(
            "pipeline_task task_id=%s attempt=%s status=success duration_ms=%s",
            task_id,
            attempt,
            round((time.monotonic() - started) * 1000),
        )
        return result
    except Exception as exc:
        _LOGGER.error(
            "pipeline_task task_id=%s attempt=%s status=failure duration_ms=%s error=%s",
            task_id,
            attempt,
            round((time.monotonic() - started) * 1000),
            str(exc),
        )
        if self.request.retries >= self.max_retries:
            record_dlq_entry(task_id, self.name, attempt, str(exc))
            raise
        raise self.retry(exc=exc, countdown=retry_countdown(self.request.retries))
