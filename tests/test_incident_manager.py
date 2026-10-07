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

def test_unexpected_error_is_safe(client, monkeypatch):
    headers = auth_headers(client)
    monkeypatch.setattr(database, "get_db", lambda: (_ for _ in ()).throw(RuntimeError("secret stack")))
    response = client.get("/api/incidents", headers=headers)
    assert response.status_code == 500 and "secret stack" not in response.text
