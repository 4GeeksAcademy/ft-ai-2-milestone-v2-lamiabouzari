from __future__ import annotations

import csv
import importlib.util
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "nightly_export.py"
spec = importlib.util.spec_from_file_location("nightly_export", MODULE_PATH)
nightly_export = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(nightly_export)


class FakeJobRunner:
    def __init__(self, processing=False, completed=False):
        self.processing = processing
        self.completed = completed
        self.calls = []

    def has_processing_lock(self, job_name):
        self.calls.append(("has_processing_lock", job_name))
        return self.processing

    def has_completed_for_date(self, job_name, target_date):
        self.calls.append(("has_completed_for_date", job_name, target_date))
        return self.completed

    def create_run(self, job_name, target_date):
        self.calls.append(("create_run", job_name, target_date))
        return "run-1"

    def mark_processing(self, run_id):
        self.calls.append(("mark_processing", run_id))
        return True

    def mark_completed(self, run_id):
        self.calls.append(("mark_completed", run_id))

    def mark_failed(self, run_id, message):
        self.calls.append(("mark_failed", run_id, message))


class RaceJobRunner(FakeJobRunner):
    """Simulate a completed run appearing after the initial pre-check."""

    def __init__(self):
        super().__init__()
        self.completed_checks = 0

    def mark_processing(self, run_id):
        self.calls.append(("mark_processing", run_id))
        return False

    def has_completed_for_date(self, job_name, target_date):
        self.completed_checks += 1
        self.calls.append(("has_completed_for_date", job_name, target_date))
        return self.completed_checks == 2


def test_target_date_override_and_utc_default(monkeypatch):
    monkeypatch.setenv("TARGET_DATE", "2026-01-15")
    assert nightly_export.target_date_from_environment() == date(2026, 1, 15)

    monkeypatch.delenv("TARGET_DATE")
    class FixedDateTime:
        @classmethod
        def now(cls, tz):
            return datetime(2026, 1, 15, 1, tzinfo=UTC)
    monkeypatch.setattr(nightly_export, "datetime", FixedDateTime)
    assert nightly_export.target_date_from_environment() == date(2026, 1, 14)


def test_duplicate_and_processing_lock_skip(monkeypatch):
    for field in ("processing", "completed"):
        fake = FakeJobRunner(**{field: True})
        monkeypatch.setattr(nightly_export, "job_runner", fake)
        nightly_export.run()
        assert not any(call[0] == "create_run" for call in fake.calls)


def test_success_exports_and_runs_pipeline(monkeypatch, tmp_path):
    fake = FakeJobRunner()
    monkeypatch.setattr(nightly_export, "job_runner", fake)
    exported = []
    monkeypatch.setattr(nightly_export, "export_telemetry", lambda target, path: exported.append(path))
    commands = []
    monkeypatch.setattr(nightly_export.subprocess, "run", lambda command, **kwargs: commands.append((command, kwargs)))
    monkeypatch.setattr(nightly_export, "_REPO_ROOT", tmp_path)
    monkeypatch.setenv("TARGET_DATE", "2026-01-15")

    nightly_export.run()

    assert exported == [tmp_path / "data/raw/telemetry_2026-01-15.csv"]
    assert commands[0][0] == [nightly_export.sys.executable, "-m", "data.pipelines.pipeline", "--triggered-by", "nightly_export"]
    assert commands[0][1] == {"cwd": tmp_path, "check": True}
    assert ("mark_completed", "run-1") in fake.calls


def test_completion_race_skips_export_and_pipeline(monkeypatch):
    fake = RaceJobRunner()
    monkeypatch.setattr(nightly_export, "job_runner", fake)
    monkeypatch.setattr(nightly_export, "export_telemetry", pytest.fail)
    monkeypatch.setattr(nightly_export.subprocess, "run", pytest.fail)

    nightly_export.run()

    assert ("mark_failed", "run-1", "Duplicate completed run exists") in fake.calls


def test_pipeline_failure_marks_run_failed(monkeypatch):
    fake = FakeJobRunner()
    monkeypatch.setattr(nightly_export, "job_runner", fake)
    monkeypatch.setattr(nightly_export, "export_telemetry", lambda target, path: None)
    monkeypatch.setattr(nightly_export.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "pipeline")))

    with pytest.raises(subprocess.CalledProcessError):
        nightly_export.run()

    failure = next(call for call in fake.calls if call[0] == "mark_failed")
    assert "returned non-zero" in failure[2]


def test_csv_header_and_existing_snapshot_not_overwritten(monkeypatch, tmp_path):
    output = tmp_path / "data" / "raw" / "telemetry_2026-01-15.csv"
    rows = [
        {
            "event_id": "event-1", "timestamp": "2026-01-15T00:00:00+00:00",
            "session_id": "session-1", "user_id": "user-1", "event_type": "view",
            "schema_version": "1", "request_id": None, "tags": {"x": 1},
        }
    ]

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params):
            return SimpleNamespace(mappings=lambda: rows)
    class Engine:
        def connect(self): return Connection()
    monkeypatch.setattr(nightly_export, "get_inventory_engine", lambda: Engine())

    nightly_export.export_telemetry(date(2026, 1, 15), output)
    with output.open(newline="", encoding="utf-8") as file:
        result = list(csv.reader(file))
    assert result[0] == nightly_export.CSV_FIELDS
    assert result[1][0] == "event-1"

    output.write_text("sentinel\n", encoding="utf-8")
    nightly_export.export_telemetry(date(2026, 1, 15), output)
    assert output.read_text(encoding="utf-8") == "sentinel\n"
