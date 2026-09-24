"""JWT, current-user, and /auth/me business-logic tests."""

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from config import settings
from dependencies import get_current_user
from routers import auth


def token_for(user_record):
    return auth._create_access_token(user_record["id"])


def test_valid_token_resolves_user(auth_db, user_record):
    result = get_current_user(token_for(user_record))
    assert str(result.id) == user_record["id"]
    assert result.email == "alice@example.com"


@pytest.mark.parametrize("token", ["not-a-jwt", jwt.encode({"exp": datetime.now(UTC) + timedelta(minutes=5)}, settings.jwt_secret, algorithm=settings.jwt_algorithm)])
def test_malformed_or_missing_subject_token_rejected(auth_db, token):
    with pytest.raises(auth.AppException) as error:
        get_current_user(token)
    assert error.value.status_code == 401


def test_expired_token_rejected(auth_db, user_record):
    token = jwt.encode({"sub": user_record["id"], "exp": datetime.now(UTC) - timedelta(minutes=1)}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(auth.AppException):
        get_current_user(token)


def test_nonexistent_user_token_rejected(auth_db):
    token = auth._create_access_token("00000000-0000-0000-0000-000000000000")
    with pytest.raises(auth.AppException):
        get_current_user(token)


def test_get_me_returns_linked_profile(auth_db, user_record):
    current = get_current_user(token_for(user_record))
    result = auth.get_me(current)
    assert result["email"] == "alice@example.com"
    assert result["profile"]["name"] == "Alice Example"


def test_get_me_reports_missing_profile(auth_db, user_record):
    auth_db.table("profiles").truncate()
    current = get_current_user(token_for(user_record))
    with pytest.raises(auth.AppException) as error:
        auth.get_me(current)
    assert error.value.status_code == 404
