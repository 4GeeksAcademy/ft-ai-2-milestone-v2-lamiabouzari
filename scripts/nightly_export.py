"""Export one UTC day of telemetry and trigger the reporting pipeline."""

from __future__ import annotations

import csv
import json
import logging
import os
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SERVICES_DIR = _REPO_ROOT / "services"
if str(_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICES_DIR))

from sqlalchemy import text

import job_runner
from database import get_inventory_engine

JOB_NAME = "nightly_export"
CSV_FIELDS = [
    "event_id", "timestamp", "session_id", "user_id", "event_type",
    "schema_version", "request_id", "tags",
]
LOGGER = logging.getLogger(JOB_NAME)


def target_date_from_environment() -> date:
    """Resolve TARGET_DATE or yesterday according to the UTC clock."""
    override = os.environ.get("TARGET_DATE")
    if override:
        return date.fromisoformat(override)
    return datetime.now(UTC).date() - timedelta(days=1)


def _json_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    return "" if value is None else str(value)


def export_telemetry(target_date: date, output_path: Path) -> Path:
    """Write the target UTC day to CSV unless its snapshot already exists."""
    if output_path.exists():
        return output_path

    start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    end = start + timedelta(days=1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    query = text(
        """
        SELECT event_id, timestamp, session_id, user_id, event_type,
               schema_version, request_id, tags
        FROM telemetry_events
        WHERE timestamp >= :start_utc AND timestamp < :end_utc
        ORDER BY timestamp, event_id
        """
    )
    with get_inventory_engine().connect() as connection:
        rows = connection.execute(query, {"start_utc": start, "end_utc": end}).mappings()
        with output_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _json_value(row[field]) for field in CSV_FIELDS})
    return output_path


def _log(level: int, event: str, target_date: date, status: str) -> None:
    LOGGER.log(
        level,
        "timestamp=%s job_name=%s status=%s target_date=%s event=%s",
        datetime.now(UTC).isoformat(), JOB_NAME, status, target_date.isoformat(), event,
    )


def run() -> None:
    target_date = target_date_from_environment()
    if job_runner.has_processing_lock(JOB_NAME):
        _log(logging.INFO, "cancelled due to processing lock", target_date, "cancelled")
        return
    if job_runner.has_completed_for_date(JOB_NAME, target_date):
        _log(logging.INFO, "skipped duplicate", target_date, "skipped duplicate")
        return

    run_id = job_runner.create_run(JOB_NAME, target_date)
    try:
        if not job_runner.mark_processing(run_id):
            if job_runner.has_completed_for_date(JOB_NAME, target_date):
                reason = "Duplicate completed run exists"
                _log(logging.INFO, "skipped duplicate", target_date, "skipped duplicate")
            else:
                reason = "Processing lock was already held"
                _log(logging.INFO, "cancelled due to processing lock", target_date, "cancelled")
            job_runner.mark_failed(run_id, reason)
            return
        _log(logging.INFO, "started", target_date, "processing")
        output_path = _REPO_ROOT / "data" / "raw" / f"telemetry_{target_date.isoformat()}.csv"
        export_telemetry(target_date, output_path)
        subprocess.run(
            [sys.executable, "-m", "data.pipelines.pipeline", "--triggered-by", JOB_NAME],
            cwd=_REPO_ROOT,
            check=True,
        )
        job_runner.mark_completed(run_id)
        _log(logging.INFO, "completed", target_date, "completed")
    except Exception as error:
        try:
            job_runner.mark_failed(run_id, str(error))
        finally:
            _log(logging.ERROR, f"failed: {error}", target_date, "failed")
        raise


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run()


if __name__ == "__main__":
    main()
