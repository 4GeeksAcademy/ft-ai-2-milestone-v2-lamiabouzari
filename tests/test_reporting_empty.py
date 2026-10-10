"""Reporting reads distinguish a missing run from a completed run with no KPI rows."""

from __future__ import annotations

from datetime import date

from sqlalchemy.exc import ProgrammingError

from reporting import router as reporting_router


class _MissingRelation(Exception):
    sqlstate = "42P01"


class _ClosedConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args, **_kwargs):
        raise ProgrammingError("SELECT", {}, _MissingRelation("relation does not exist"))


class _MissingEngine:
    def connect(self):
        return _ClosedConnection()


def test_missing_weekly_table_returns_empty_report(auth_client, registered_user, monkeypatch):
    monkeypatch.setattr(reporting_router, "get_inventory_engine", lambda: _MissingEngine())
    login = auth_client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse"},
    )
    assert login.status_code == 200, login.text

    response = auth_client.get(
        "/reporting/weekly-warehouse-client-performance",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "week_start": None,
        "entries": [],
        "report_state": "never_run",
    }


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _RunConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, _params=None):
        sql = str(statement)
        if "MAX(week_start)" in sql:
            return _Rows([{"week_start": None}])
        if "FROM reporting.pipeline_runs" in sql:
            return _Rows(
                [
                    {
                        "run_id": "run-1",
                        "started_at": None,
                        "completed_at": None,
                        "records_processed": 0,
                        "status": "Completed",
                        "error_details": None,
                        "week_start": date(2026, 9, 14),
                        "week_end": date(2026, 9, 21),
                        "triggered_by": "api",
                    }
                ]
            )
        if "FROM telemetry_events" in sql:
            return _Rows(
                [
                    {
                        "source_events": 2,
                        "missing_client_id": 2,
                        "missing_warehouse": 0,
                    }
                ]
            )
        return _Rows([])


class _RunEngine:
    def connect(self):
        return _RunConnection()


def test_completed_run_with_no_rows_reports_missing_client_id(
    auth_client, registered_user, monkeypatch
):
    monkeypatch.setattr(reporting_router, "get_inventory_engine", lambda: _RunEngine())
    login = auth_client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse"},
    )
    assert login.status_code == 200, login.text

    response = auth_client.get(
        "/reporting/weekly-warehouse-client-performance",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "week_start": "2026-09-14",
        "entries": [],
        "report_state": "completed_without_rows",
        "pipeline_run": {
            "status": "Completed",
            "records_processed": 0,
            "week_start": "2026-09-14",
            "week_end": "2026-09-21",
        },
        "source_gap": {
            "source_events": 2,
            "missing_client_id": 2,
            "missing_warehouse": 0,
        },
    }
