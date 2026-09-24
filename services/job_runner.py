"""Persistence helpers for background-process runs."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from database import get_inventory_engine


def create_run(job_name: str, target_date: date) -> str:
    """Create a pending run and return its UUID as a string."""
    run_id = uuid.uuid4()
    with get_inventory_engine().begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO job_runs (id, job_name, target_date, status)
                VALUES (:id, :job_name, :target_date, 'pending')
                """
            ),
            {"id": run_id, "job_name": job_name, "target_date": target_date},
        )
    return str(run_id)


def mark_processing(run_id: str) -> bool:
    """Atomically claim a pending run as the job's processing lock."""
    try:
        with get_inventory_engine().begin() as connection:
            result = connection.execute(
                text(
                    """
                    UPDATE job_runs AS candidate
                    SET status = 'processing', started_at = CURRENT_TIMESTAMP
                    WHERE candidate.id = :run_id
                      AND candidate.status = 'pending'
                                            AND NOT EXISTS (
                                                    SELECT 1
                                                    FROM job_runs AS completed
                                                    WHERE completed.job_name = candidate.job_name
                                                        AND completed.target_date = candidate.target_date
                                                        AND completed.status = 'completed'
                                            )
                    """
                ),
                {"run_id": run_id},
            )
    except IntegrityError:
        # Another process won the partial unique-index race.
        return False
    return result.rowcount == 1


def mark_completed(run_id: str) -> None:
    """Mark a claimed run completed."""
    with get_inventory_engine().begin() as connection:
        connection.execute(
            text(
                """
                UPDATE job_runs
                SET status = 'completed', finished_at = CURRENT_TIMESTAMP,
                    error_message = NULL
                WHERE id = :run_id
                """
            ),
            {"run_id": run_id},
        )


def mark_failed(run_id: str, error_message: str) -> None:
    """Mark a run failed and persist the failure text."""
    with get_inventory_engine().begin() as connection:
        connection.execute(
            text(
                """
                UPDATE job_runs
                SET status = 'failed', finished_at = CURRENT_TIMESTAMP,
                    error_message = :error_message
                WHERE id = :run_id
                """
            ),
            {"run_id": run_id, "error_message": error_message},
        )


def has_processing_lock(job_name: str) -> bool:
    """Return whether any run currently owns the processing lock."""
    with get_inventory_engine().connect() as connection:
        return bool(
            connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM job_runs
                        WHERE job_name = :job_name AND status = 'processing'
                    )
                    """
                ),
                {"job_name": job_name},
            ).scalar()
        )


def has_completed_for_date(job_name: str, target_date: date) -> bool:
    """Return whether this job already completed for the target date."""
    with get_inventory_engine().connect() as connection:
        return bool(
            connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM job_runs
                        WHERE job_name = :job_name
                          AND target_date = :target_date
                          AND status = 'completed'
                    )
                    """
                ),
                {"job_name": job_name, "target_date": target_date},
            ).scalar()
        )
