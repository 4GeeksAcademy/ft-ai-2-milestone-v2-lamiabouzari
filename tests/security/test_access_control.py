"""Access-control proofs for unauthenticated data routes and user IDOR."""

from __future__ import annotations

from types import SimpleNamespace

from reporting import router as reporting_router


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_anonymous_callers_cannot_read_incidents_inventory_or_client_kpis(auth_client):
    denied = [
        auth_client.get("/api/incidents"),
        auth_client.get("/api/incidents/summary"),
        auth_client.get("/inventory/orders"),
        auth_client.get("/inventory/products"),
        auth_client.get("/reporting/weekly-warehouse-client-performance"),
        auth_client.get("/telemetry/report"),
        auth_client.get("/tasks/task-1"),
        auth_client.post("/agent/query", json={"question": "Where is order #12345?"}),
        auth_client.post("/knowledge/query", json={"question": "What is the Spain SLA?"}),
        auth_client.get("/events/stream"),
    ]
    assert [response.status_code for response in denied] == [401] * len(denied)


def test_unauthenticated_pipeline_trigger_does_not_enqueue(auth_client, registered_user, monkeypatch):
    calls = []

    def fake_apply_async(*, args):
        calls.append(args)
        return SimpleNamespace(id="celery-123")

    monkeypatch.setattr(
        reporting_router.run_weekly_warehouse_client_performance,
        "apply_async",
        fake_apply_async,
    )

    anonymous = auth_client.post("/reporting/pipeline-runs?week_start=2026-09-14")
    assert anonymous.status_code == 401
    assert calls == []

    headers = _login(auth_client, "alice@example.com", "correct-horse")
    accepted = auth_client.post(
        "/reporting/pipeline-runs?week_start=2026-09-14",
        headers=headers,
    )
    assert accepted.status_code == 202
    assert accepted.json() == {"task_id": "celery-123"}
    assert calls == [["2026-09-14"]]


def test_authenticated_operator_can_list_incidents(auth_client, registered_user):
    headers = _login(auth_client, "alice@example.com", "correct-horse")
    response = auth_client.get("/api/incidents", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_invalid_jwt_is_rejected(auth_client):
    response = auth_client.get(
        "/api/incidents",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401


def test_user_cannot_list_directory_or_read_another_user(auth_client, registered_user, user_record):
    alice = _login(auth_client, "alice@example.com", "correct-horse")
    created = auth_client.post(
        "/auth/register",
        json={
            "email": "bob@example.com",
            "password": "correct-horse",
            "display_name": "Bob",
        },
    )
    assert created.status_code == 201, created.text
    bob_id = created.json()["id"]

    assert auth_client.get("/users", headers=alice).status_code == 403
    other = auth_client.get(f"/users/{bob_id}", headers=alice)
    assert other.status_code == 403
    assert "bob@example.com" not in other.text

    own = auth_client.get(f"/users/{user_record['id']}", headers=alice)
    assert own.status_code == 200
    assert own.json()["email"] == "alice@example.com"
    assert "password" not in own.json()
