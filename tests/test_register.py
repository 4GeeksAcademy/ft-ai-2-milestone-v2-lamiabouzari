"""Registration business-logic tests."""

import pytest
from pydantic import ValidationError

from routers import auth


def registration_body(**changes):
    value = {
        "email": "alice@example.com",
        "password": "correct-horse",
        "display_name": "Alice",
        "name": "Alice Example",
        "phone": "555-0100",
        "address": "1 Main Street",
    }
    value.update(changes)
    return auth.UserCreate(**value)


def test_register_persists_hashed_user_profile_and_default_role(auth_db):
    result = auth.register(registration_body())
    user = auth_db.table("users").all()[0]
    profile = auth_db.table("profiles").all()[0]

    assert result["email"] == "alice@example.com"
    assert result["role"] == "user"
    assert user["hashed_password"] != "correct-horse"
    assert user["hashed_password"].startswith("$2b$")
    assert user["role"] == "user"
    assert profile["user_id"] == user["id"]
    assert profile["name"] == "Alice Example"


def test_register_rejects_duplicate_email(auth_db):
    auth.register(registration_body())
    with pytest.raises(auth.AppException) as error:
        auth.register(registration_body())
    assert error.value.status_code == 409


@pytest.mark.parametrize("password", ["", "short"])
def test_registration_rejects_short_password(password):
    with pytest.raises(ValidationError):
        registration_body(password=password)


def test_registration_rejects_too_long_password():
    with pytest.raises(auth.AppException) as error:
        registration_body(password="x" * 129)
    assert error.value.status_code == 422
