"""Supplier directory tests. They use a temporary TinyDB file, never services/data/db.json."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1] / "services"))

import database
from api.seed import SUPPLIERS_SEED, seed_suppliers
from database import _create_storage
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    database._db = _create_storage(str(tmp_path / "db.json"))
    # Supplier tests must not open Postgres or copy the live TinyDB file.
    monkeypatch.setattr("main.create_inventory_db_and_tables", lambda: None)
    monkeypatch.setattr("main.backup_db", lambda: None)
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(client: TestClient) -> dict[str, str]:
    registered = client.post(
        "/auth/register",
        json={"email": "supplier-tests@example.com", "password": "correct-horse", "display_name": "Supplier Tests"},
    )
    assert registered.status_code == 201, registered.text
    login = client.post("/auth/login", json={"email": "supplier-tests@example.com", "password": "correct-horse"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def supplier_payload(**changes):
    payload = {
        "name": "Harbor Cartage",
        "country": "USA",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 8.25,
        "currency": "USD",
        "status": "active",
        "service_zone": "Los Angeles",
        "contact_email": "ops@harbor.example",
        "notes": "Test supplier",
    }
    payload.update(changes)
    return payload


def test_create_returns_id_and_server_timestamp(client):
    headers = auth_headers(client)
    response = client.post("/suppliers", json=supplier_payload(), headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["name"] == "Harbor Cartage"
    assert body["rate_per_shipment"] == 8.25
    assert body["updated_at"].endswith(("Z", "+00:00"))


def test_required_and_context_validation(client):
    headers = auth_headers(client)
    blank = client.post("/suppliers", json=supplier_payload(name="   "), headers=headers)
    assert blank.status_code == 422
    assert client.post("/suppliers", json=supplier_payload(categories=[]), headers=headers).status_code == 422
    assert client.post("/suppliers", json=supplier_payload(categories=["not_a_category"]), headers=headers).status_code == 422
    assert client.post("/suppliers", json=supplier_payload(country="France", currency="EUR"), headers=headers).status_code == 422
    mismatch = client.post("/suppliers", json=supplier_payload(country="Spain", currency="USD"), headers=headers)
    assert mismatch.status_code == 422
    assert "EUR" in mismatch.json()["detail"]
    assert client.post("/suppliers", json=supplier_payload(status="paused"), headers=headers).status_code == 422
    assert database._db.table("suppliers").all() == []


@pytest.mark.parametrize("rate", [0, -1, -0.01])
def test_zero_and_negative_rates_are_rejected(client, rate):
    headers = auth_headers(client)
    response = client.post("/suppliers", json=supplier_payload(rate_per_shipment=rate), headers=headers)
    assert response.status_code == 422
    assert database._db.table("suppliers").all() == []


def post_json(client: TestClient, payload: dict, headers: dict[str, str]):
    return client.post(
        "/suppliers",
        content=json.dumps(payload),
        headers={**headers, "Content-Type": "application/json"},
    )


def test_non_finite_rates_are_rejected(client):
    headers = auth_headers(client)
    for rate in (float("nan"), float("inf"), float("-inf")):
        response = post_json(client, supplier_payload(rate_per_shipment=rate), headers)
        assert response.status_code == 422
    assert database._db.table("suppliers").all() == []


def test_client_updated_at_is_rejected_before_write(client):
    headers = auth_headers(client)
    response = client.post(
        "/suppliers",
        json=supplier_payload(updated_at="2020-01-01T00:00:00+00:00"),
        headers=headers,
    )
    assert response.status_code == 422
    assert "updated_at" in response.json()["detail"]
    assert database._db.table("suppliers").all() == []


def test_list_filters(client):
    headers = auth_headers(client)
    assert seed_suppliers() == len(SUPPLIERS_SEED)
    everyone = client.get("/suppliers", headers=headers)
    assert everyone.status_code == 200
    assert len(everyone.json()) == 15
    usa = client.get("/suppliers", params={"country": "USA"}, headers=headers)
    assert {row["country"] for row in usa.json()} == {"USA"}
    packaging = client.get("/suppliers", params={"category": "packaging_materials"}, headers=headers)
    assert {row["name"] for row in packaging.json()} == {"PackSource LA", "Embalajes Zaragoza S.L."}
    combined = client.get(
        "/suppliers",
        params={"country": "Spain", "category": "carrier_international"},
        headers=headers,
    )
    assert [row["name"] for row in combined.json()] == ["DHL Express España"]
    assert client.get("/suppliers", params={"country": "Mexico"}, headers=headers).status_code == 422


def test_detail_and_unknown_ids(client):
    headers = auth_headers(client)
    created = client.post("/suppliers", json=supplier_payload(), headers=headers).json()
    detail = client.get(f"/suppliers/{created['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["name"] == "Harbor Cartage"
    missing = 999999
    assert client.get(f"/suppliers/{missing}", headers=headers).status_code == 404
    assert client.patch(f"/suppliers/{missing}/rate", json={"rate_per_shipment": 2}, headers=headers).status_code == 404
    assert client.patch(f"/suppliers/{missing}/status", json={"status": "suspended"}, headers=headers).status_code == 404
    assert client.delete(f"/suppliers/{missing}", headers=headers).status_code == 404
    assert client.get("/suppliers/not-an-id", headers=headers).status_code == 422


def test_rate_and_status_updates(client):
    headers = auth_headers(client)
    created = client.post("/suppliers", json=supplier_payload(), headers=headers).json()
    supplier_id = created["id"]
    assert client.patch(f"/suppliers/{supplier_id}/rate", json={"rate_per_shipment": 0}, headers=headers).status_code == 422
    assert client.patch(f"/suppliers/{supplier_id}/rate", json={"rate_per_shipment": -3}, headers=headers).status_code == 422
    non_finite = client.patch(
        f"/suppliers/{supplier_id}/rate",
        content=json.dumps({"rate_per_shipment": math.nan}),
        headers={**headers, "Content-Type": "application/json"},
    )
    assert non_finite.status_code == 422
    unchanged = client.get(f"/suppliers/{supplier_id}", headers=headers).json()
    assert unchanged["rate_per_shipment"] == 8.25
    assert unchanged["updated_at"] == created["updated_at"]
    updated = client.patch(f"/suppliers/{supplier_id}/rate", json={"rate_per_shipment": 9.5}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["rate_per_shipment"] == 9.5
    assert updated.json()["updated_at"] != created["updated_at"]
    rejected = client.patch(f"/suppliers/{supplier_id}/status", json={"status": "archived"}, headers=headers)
    assert rejected.status_code == 422
    status_response = client.patch(f"/suppliers/{supplier_id}/status", json={"status": "suspended"}, headers=headers)
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "suspended"
    assert status_response.json()["updated_at"] == updated.json()["updated_at"]
    assert status_response.json()["rate_per_shipment"] == 9.5


def test_delete(client):
    headers = auth_headers(client)
    created = client.post("/suppliers", json=supplier_payload(), headers=headers).json()
    deleted = client.delete(f"/suppliers/{created['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"id": created["id"], "detail": "Supplier deleted."}
    assert client.get(f"/suppliers/{created['id']}", headers=headers).status_code == 404


def test_seeder_is_idempotent_and_preserves_edits(client, tmp_path):
    assert seed_suppliers() == 15
    names = {row["name"] for row in database._db.table("suppliers").all()}
    assert names == {item["name"] for item in SUPPLIERS_SEED}
    assert seed_suppliers() == 0
    assert len(database._db.table("suppliers").all()) == 15
    document = next(row for row in database._db.table("suppliers").all() if row["name"] == "UPS Ground")
    database._db.table("suppliers").update(
        {"rate_per_shipment": 3.33, "status": "suspended", "updated_at": "2024-01-01T00:00:00+00:00"},
        doc_ids=[document.doc_id],
    )
    assert seed_suppliers() == 0
    preserved = database._db.table("suppliers").get(doc_id=document.doc_id)
    assert preserved["rate_per_shipment"] == 3.33
    assert preserved["status"] == "suspended"
    assert preserved["updated_at"] == "2024-01-01T00:00:00+00:00"


def test_records_persist_after_reopen(tmp_path):
    path = tmp_path / "db.json"
    database._db = _create_storage(str(path))
    assert seed_suppliers() == 15
    database._db.close()
    database._db = _create_storage(str(path))
    stored = database._db.table("suppliers").all()
    assert len(stored) == 15
    assert {row["name"] for row in stored} == {item["name"] for item in SUPPLIERS_SEED}


def test_seed_does_not_touch_other_tables(client):
    database._db.table("users").insert({"email": "keep@example.com", "role": "admin"})
    database._db.table("incident_analysis_reports").insert({"filename": "kept.csv"})
    assert seed_suppliers() == 15
    assert database._db.table("users").all()[0]["email"] == "keep@example.com"
    assert database._db.table("incident_analysis_reports").all()[0]["filename"] == "kept.csv"


def test_suppliers_require_authentication(client):
    assert client.get("/suppliers").status_code == 401
