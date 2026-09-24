"""Shared isolated fixtures for authentication tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tinydb import TinyDB
from tinydb.storages import MemoryStorage

SERVICES_DIR = Path(__file__).parents[1] / "services"
ROOT_DIR = SERVICES_DIR.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(SERVICES_DIR))

import database  # noqa: E402
import dependencies  # noqa: E402
from routers import auth  # noqa: E402
from routers import profiles  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def auth_db(monkeypatch: pytest.MonkeyPatch) -> TinyDB:
    """Provide one in-memory TinyDB instance to every auth code path."""
    db = TinyDB(storage=MemoryStorage)
    monkeypatch.setattr(database, "get_db", lambda: db)
    monkeypatch.setattr(auth, "get_db", lambda: db)
    monkeypatch.setattr(profiles, "get_db", lambda: db)
    monkeypatch.setattr(dependencies, "get_db", lambda: db)
    return db


@pytest.fixture
def registered_user(auth_db: TinyDB):
    body = auth.UserCreate(
        email="alice@example.com",
        password="correct-horse",
        display_name="Alice",
        name="Alice Example",
        phone="555-0100",
        address="1 Main Street",
    )
    auth.register(body)
    return body


@pytest.fixture
def user_record(auth_db: TinyDB, registered_user):
    return auth_db.table("users").all()[0]


@pytest.fixture
def auth_client(auth_db: TinyDB):
    app.dependency_overrides[database.get_db] = lambda: auth_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


