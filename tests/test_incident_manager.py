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

def auth_headers(client):
    registered = client.post("/auth/register", json={
        "email": "alice@example.com",
        "password": "correct-horse",
        "display_name": "Alice",
    })
    assert registered.status_code == 201, registered.text
    login = client.post("/auth/login", json={"email": "alice@example.com", "password": "correct-horse"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}

def test_empty_list_and_summary_are_zero(client):
    headers = auth_headers(client)
    assert client.get("/api/incidents", headers=headers).json() == []
    summary = client.get("/api/incidents/summary", headers=headers).json()
    assert all(count == 0 for group in summary.values() for count in group.values())

def test_create_filters_and_lifecycle(client):
    headers = auth_headers(client)
    response = client.post("/api/incidents", json=payload(), headers=headers)
    assert response.status_code == 201
    incident_id = response.json()["id"]
    assert len(client.get("/api/incidents", params={"branch":"central"}, headers=headers).json()) == 1
    assert client.patch(f"/api/incidents/{incident_id}/status", json={"status":"in_progress"}, headers=headers).status_code == 200
    assert client.patch(f"/api/incidents/{incident_id}/status", json={"status":"resolved"}, headers=headers).status_code == 200
    invalid = client.patch(f"/api/incidents/{incident_id}/status", json={"status":"open"}, headers=headers)
    assert invalid.status_code == 400 and invalid.json()["detail"]["field"] == "status"

def test_invalid_post_is_400_and_missing_is_404(client):
    headers = auth_headers(client)
    response = client.post("/api/incidents", json=payload(branch="not-a-branch"), headers=headers)
    assert response.status_code == 400 and response.json()["detail"]["field"] == "branch"
    assert client.get("/api/incidents/00000000-0000-0000-0000-000000000000", headers=headers).status_code == 404

def test_original_csv_analysis_does_not_write_incidents(client):
    headers = auth_headers(client)
    csv_path = Path(__file__).parents[1] / "scripts" / "incidents-trackflow.csv"
    with csv_path.open("rb") as handle:
        response = client.post(
            "/api/incidents/analyze",
            headers=headers,
            files={"file": ("incidents-trackflow.csv", handle, "text/csv")},
        )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["total_records"] == 100
    assert report["valid_records"] == 95
    assert report["invalid_records"] == 5
    assert report["invalid_by_reason"] == {
        "closed_without_satisfaction_score": 1,
        "invalid_carrier": 1,
        "invalid_category": 1,
        "invalid_customer_email": 1,
        "invalid_tracking_number": 1,
    }
    assert sum(report["category_breakdown"].values()) == 95
    assert sum(report["status_breakdown"].values()) == 95
    assert sum(report["country_breakdown"].values()) == 95
    assert report["average_satisfaction"] is not None
    assert report["filename"] == "incidents-trackflow.csv"
    assert report["analyzed_at"]
    assert "@" not in response.text
    assert client.get("/api/incidents", headers=headers).json() == []
    saved = database.get_db().table("incident_analysis_reports").all()
    assert len(saved) == 1
    assert "description" not in saved[0]
    assert "@" not in str(saved[0])


def test_saved_analysis_reloads_without_changing_other_tables(client, tmp_path):
    headers = auth_headers(client)
    db = database.get_db()
    before = {name: len(db.table(name)) for name in ("users", "profiles", "_default")}
    csv_path = Path(__file__).parents[1] / "scripts" / "incidents-trackflow.csv"
    with csv_path.open("rb") as handle:
        created = client.post(
            "/api/incidents/analyze",
            headers=headers,
            files={"file": ("../secret/incidents-trackflow.csv", handle, "text/csv")},
        )
    assert created.status_code == 200, created.text
    database._db.close()
    database._db = database._create_storage(str(tmp_path / "db.json"))
    loaded = client.get("/api/incidents/analysis", headers=headers)
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["filename"] == "incidents-trackflow.csv"
    assert loaded.json()["valid_records"] == 95
    assert client.get("/api/incidents/results/export", headers=headers).status_code == 200
    after = database.get_db()
    assert len(after.table("users")) == before["users"]
    assert len(after.table("profiles")) == before["profiles"]
    assert len(after.table("_default")) == before["_default"]
    assert client.get("/api/incidents", headers=headers).json() == []


def test_unexpected_error_is_safe(client, monkeypatch):
    headers = auth_headers(client)
    monkeypatch.setattr(database, "get_db", lambda: (_ for _ in ()).throw(RuntimeError("secret stack")))
    response = client.get("/api/incidents", headers=headers)
    assert response.status_code == 500 and "secret stack" not in response.text
