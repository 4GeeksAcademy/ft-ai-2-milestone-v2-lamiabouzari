"""Login business-logic tests."""

import pytest
from jose import jwt

from config import settings
from routers import auth
from models.user import User
from tests.test_register import registration_body


def test_login_returns_jwt_for_valid_credentials(auth_db):
    auth.register(registration_body())
    result = auth.login(auth.UserLogin(email="alice@example.com", password="correct-horse"))
    payload = jwt.decode(result["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert result["token_type"] == "bearer"
    assert payload["sub"] == result["user"]["id"]


@pytest.mark.parametrize("email,password", [("alice@example.com", "wrong"), ("nobody@example.com", "correct-horse")])
def test_login_rejects_wrong_or_unknown_credentials(auth_db, email, password):
    auth.register(registration_body())
    with pytest.raises(auth.AppException) as error:
        auth.login(auth.UserLogin(email=email, password=password))
    assert error.value.status_code == 401


def test_login_rejects_inactive_users(auth_db):
    auth.register(registration_body())
    table = auth_db.table("users")
    doc = table.all()[0]
    table.update({"is_active": False}, doc_ids=[doc.doc_id])
    with pytest.raises(auth.AppException) as error:
        auth.login(auth.UserLogin(email="alice@example.com", password="correct-horse"))
    assert error.value.status_code == 401
