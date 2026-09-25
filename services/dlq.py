"""Durable persistence for tasks that have exhausted their retries."""

from __future__ import annotations

from sqlalchemy import text

from database import get_inventory_engine


def record_dlq_entry(
    task_id: str, task_name: str, attempt: int, error_message: str
) -> None:
    """Insert one exhausted task, safely ignoring duplicate deliveries."""
    with get_inventory_engine().begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO dlq_tasks (task_id, task_name, attempt, error_message)
                VALUES (:task_id, :task_name, :attempt, :error_message)
                ON CONFLICT (task_id) DO NOTHING
                """
            ),
            {
                "task_id": task_id,
                "task_name": task_name,
                "attempt": attempt,
                "error_message": error_message,
            },
        )
