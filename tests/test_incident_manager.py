import sys
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1] / "services"))
from database import _create_storage
import database
from main import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    database._db = _create_storage(str(tmp_path / "db.json"))
    return TestClient(app)

def payload(**changes):
    value = {"title":"Package issue", "description":"A package needs attention", "category":"damage", "origin":"internal", "branch":"central"}
    value.update(changes); return value

def test_empty_list_and_summary_are_zero(client):
    assert client.get("/api/incidents").json() == []
    summary = client.get("/api/incidents/summary").json()
    assert all(count == 0 for group in summary.values() for count in group.values())

def test_create_filters_and_lifecycle(client):
    response = client.post("/api/incidents", json=payload())
    assert response.status_code == 201
    incident_id = response.json()["id"]
    assert len(client.get("/api/incidents", params={"branch":"central"}).json()) == 1
    assert client.patch(f"/api/incidents/{incident_id}/status", json={"status":"in_progress"}).status_code == 200
    assert client.patch(f"/api/incidents/{incident_id}/status", json={"status":"resolved"}).status_code == 200
    invalid = client.patch(f"/api/incidents/{incident_id}/status", json={"status":"open"})
    assert invalid.status_code == 400 and invalid.json()["detail"]["field"] == "status"

def test_invalid_post_is_400_and_missing_is_404(client):
    response = client.post("/api/incidents", json=payload(branch="not-a-branch"))
    assert response.status_code == 400 and response.json()["detail"]["field"] == "branch"
    assert client.get("/api/incidents/00000000-0000-0000-0000-000000000000").status_code == 404

def test_unexpected_error_is_safe(client, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: (_ for _ in ()).throw(RuntimeError("secret stack")))
    response = client.get("/api/incidents")
    assert response.status_code == 500 and "secret stack" not in response.text
