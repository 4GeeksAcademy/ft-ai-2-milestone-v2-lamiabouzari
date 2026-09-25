"""Task status endpoints backed by Celery's result backend."""

from __future__ import annotations

from typing import Any

from celery.result import AsyncResult
from fastapi import APIRouter

from celery_app import celery_app

router = APIRouter(tags=["tasks"])

_STATUS_MAP = {"PENDING": "pending", "STARTED": "started", "SUCCESS": "success", "FAILURE": "failure"}


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str) -> dict[str, Any]:
    """Return a safe, normalized view of a Celery task result."""
    result = AsyncResult(task_id, app=celery_app)
    status = _STATUS_MAP.get(result.state, "pending")
    response: dict[str, Any] = {"task_id": task_id, "status": status, "result": None}
    if status == "success":
        response["result"] = result.result
    elif status == "failure":
        response["result"] = {"error": "Task failed"}
    return response
