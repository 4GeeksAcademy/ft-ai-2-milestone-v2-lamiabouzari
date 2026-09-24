"""Profile update business-logic tests."""

import pytest

from models.profile import ProfileUpdate
from routers import auth, profiles
from tests.test_register import registration_body


def current_user_for(user_record):
    return auth.get_current_user(auth._create_access_token(user_record["id"]))


def test_owner_updates_profile_without_changing_user(auth_db):
    auth.register(registration_body())
    user_before = auth_db.table("users").all()[0].copy()
    user = current_user_for(user_before)

    result = profiles.update_my_profile(
        ProfileUpdate(name="Updated Alice", phone="555-0199"), user, auth_db
    )

    assert result.name == "Updated Alice"
    assert result.phone == "555-0199"
    assert auth_db.table("users").all()[0] == user_before
    stored = auth_db.table("profiles").all()[0]
    assert stored["address"] == "1 Main Street"


def test_empty_optional_phone_is_accepted_and_persisted(auth_db):
    auth.register(registration_body())
    user = current_user_for(auth_db.table("users").all()[0])

    result = profiles.update_my_profile(ProfileUpdate(phone=""), user, auth_db)

    assert result.phone == ""
    assert auth_db.table("profiles").all()[0]["phone"] == ""


def test_profile_update_without_authentication_is_rejected(auth_client):
    response = auth_client.put("/profiles/me", json={"name": "Unauthenticated"})
    assert response.status_code == 401
