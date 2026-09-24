"""Password reset, change, and helper business-logic tests."""

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from config import settings
from dependencies import get_current_user
from routers import auth
from tests.test_register import registration_body


def persisted_user(auth_db):
    auth.register(registration_body())
    return auth_db.table("users").all()[0]


def test_reset_request_is_generic_and_existing_email_sends_token(auth_db, monkeypatch):
    persisted_user(auth_db)
    sent = []
    monkeypatch.setattr(auth, "_send_reset_email", lambda email, token: sent.append((email, token)))
    expected = {"detail": "If an account with that email exists, a reset link has been sent."}
    assert auth.forgot_password(auth.RequestResetLinkRequest(email="alice@example.com")) == expected
    assert auth.request_reset_link(auth.RequestResetLinkRequest(email="alice@example.com")) == expected
    assert sent and sent[0][0] == "alice@example.com"
    assert auth._decode_reset_token(sent[0][1])[0] == auth_db.table("users").all()[0]["id"]


def test_reset_request_does_not_reveal_unknown_email(auth_db, monkeypatch):
    sent = []
    monkeypatch.setattr(auth, "_send_reset_email", lambda *args: sent.append(args))
    result = auth.forgot_password(auth.RequestResetLinkRequest(email="unknown@example.com"))
    assert result["detail"].startswith("If an account")
    assert sent == []


def test_reset_password_changes_and_hashes_password(auth_db):
    user = persisted_user(auth_db)
    token = auth._create_reset_token(user["id"])
    result = auth.reset_password(auth.ResetPasswordRequest(token=token, new_password="new-password"))
    updated = auth_db.table("users").all()[0]
    assert result["detail"] == "Password has been reset successfully."
    assert updated["hashed_password"] != "new-password"
    assert auth.pwd_context.verify("new-password", updated["hashed_password"])


def test_reset_password_rejects_bad_purpose_missing_user_and_reuse(auth_db):
    user = persisted_user(auth_db)
    bad_purpose = jwt.encode({"sub": user["id"], "purpose": "access", "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(minutes=5)}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(auth.AppException):
        auth.reset_password(auth.ResetPasswordRequest(token=bad_purpose, new_password="new-password"))
    missing = auth._create_reset_token("00000000-0000-0000-0000-000000000000")
    with pytest.raises(auth.AppException):
        auth.reset_password(auth.ResetPasswordRequest(token=missing, new_password="new-password"))
    token = auth._create_reset_token(user["id"])
    auth.reset_password(auth.ResetPasswordRequest(token=token, new_password="new-password"))
    with pytest.raises(auth.AppException):
        auth.reset_password(auth.ResetPasswordRequest(token=token, new_password="another-password"))


def test_change_password_checks_current_password_and_hashes(auth_db):
    user = persisted_user(auth_db)
    current = get_current_user(auth._create_access_token(user["id"]))
    with pytest.raises(auth.AppException):
        auth.change_password(auth.ChangePasswordRequest(current_password="wrong", new_password="new-password"), current)
    result = auth.change_password(auth.ChangePasswordRequest(current_password="correct-horse", new_password="new-password"), current)
    updated = auth_db.table("users").all()[0]
    assert result["detail"] == "Password updated successfully."
    assert auth.pwd_context.verify("new-password", updated["hashed_password"])


def test_helpers_build_expected_values():
    assert auth._gravatar_url(" Alice@Example.com ") == "https://www.gravatar.com/avatar/c160f8cc69a4f0bf2b0362752353d060?d=identicon&s=200"
    token = auth._create_access_token("subject")
    assert auth._decode_reset_token(auth._create_reset_token("subject"))[0] == "subject"
    assert auth._build_frontend_reset_link(token).startswith(settings.frontend_base_url)
