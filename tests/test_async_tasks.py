from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "services"))

from celery.exceptions import Retry  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import dlq  # noqa: E402
import routers.tasks as task_router  # noqa: E402
from main import app  # noqa: E402
from reporting import router as reporting_router  # noqa: E402
from tasks import pipeline_tasks  # noqa: E402


def test_trigger_returns_celery_id_and_serializes_week(monkeypatch):
    captured = {}

    def fake_apply_async(*, args):
        captured["args"] = args
        return SimpleNamespace(id="celery-123")

    monkeypatch.setattr(reporting_router.run_weekly_warehouse_client_performance, "apply_async", fake_apply_async)
    with TestClient(app) as client:
        response = client.post("/reporting/pipeline-runs?week_start=2026-09-14")

    assert response.status_code == 202
    assert response.json() == {"task_id": "celery-123"}
    assert captured["args"] == ["2026-09-14"]


def test_task_success_converts_date(monkeypatch):
    received = {}

    def fake_pipeline(*, week_start, triggered_by):
        received.update(week_start=week_start, triggered_by=triggered_by)
        return 7

    monkeypatch.setattr(pipeline_tasks, "record_dlq_entry", pytest.fail)
    monkeypatch.setitem(sys.modules, "pipeline", SimpleNamespace(weekly_warehouse_client_performance_pipeline=fake_pipeline))
    task = pipeline_tasks.run_weekly_warehouse_client_performance
    monkeypatch.setattr(task, "retry", pytest.fail)
    task.app.conf.task_always_eager = True
    assert task.apply(args=["2026-09-14"], throw=True).result == 7
    assert received == {"week_start": date(2026, 9, 14), "triggered_by": "api"}


@pytest.mark.parametrize("retries,countdown", [(0, 10), (1, 20), (2, 40)])
def test_task_retry_backoff(monkeypatch, retries, countdown):
    monkeypatch.setitem(sys.modules, "pipeline", SimpleNamespace(weekly_warehouse_client_performance_pipeline=lambda **_: (_ for _ in ()).throw(RuntimeError("boom"))))
    assert pipeline_tasks.retry_countdown(retries) == countdown


def test_final_failure_records_dlq_once(monkeypatch):
    entries = []
    monkeypatch.setattr(dlq, "record_dlq_entry", lambda *args: entries.append(args))
    monkeypatch.setattr(pipeline_tasks, "record_dlq_entry", dlq.record_dlq_entry)
    monkeypatch.setitem(sys.modules, "pipeline", SimpleNamespace(weekly_warehouse_client_performance_pipeline=lambda **_: (_ for _ in ()).throw(ValueError("bad"))))
    task = pipeline_tasks.run_weekly_warehouse_client_performance
    task.push_request(id="task-final", retries=3)
    try:
        with pytest.raises(ValueError, match="bad"):
            task.run(None)
    finally:
        task.pop_request()

    assert entries == [("task-final", "tasks.weekly_warehouse_client_performance", 4, "bad")]
    assert pipeline_tasks.run_weekly_warehouse_client_performance.max_retries == 3


@pytest.mark.parametrize("celery_state,public_state", [("PENDING", "pending"), ("STARTED", "started"), ("SUCCESS", "success"), ("FAILURE", "failure")])
def test_task_status_mapping(monkeypatch, celery_state, public_state):
    result = SimpleNamespace(state=celery_state, result={"value": 1})
    monkeypatch.setattr(task_router, "AsyncResult", lambda task_id, app: result)
    response = task_router.get_task_status("task-1")
    assert response["status"] == public_state
    if public_state == "failure":
        assert response["result"] == {"error": "Task failed"}
    elif public_state == "success":
        assert response["result"] == {"value": 1}
    else:
        assert response["result"] is None
