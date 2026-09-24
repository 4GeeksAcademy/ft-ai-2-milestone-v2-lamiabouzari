"""Authentication router endpoints for register/login and password management."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import resend
from fastapi import APIRouter, Depends, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from requests import RequestException

from config import settings
from database import get_db
from dependencies import get_current_user
from exceptions import (
    ERROR_CODES,
    AppException,
    email_already_exists,
    invalid_credentials,
    token_invalid,
)
from models.profile import Profile, ProfilePublic
from models.user import (
    ChangePasswordRequest,
    RequestResetLinkRequest,
    ResetPasswordRequest,
    User,
    UserCreate,
    UserLogin,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)


@router.get("/me")
def get_me(current_user: UserPublic = Depends(get_current_user)) -> dict:
    """Return the currently authenticated user and linked profile."""
    db = get_db()
    profiles_table = db.table("profiles")

    matching = profiles_table.search(
        lambda doc: doc.get("user_id") == str(current_user.id)
    )
    if not matching:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
            error_code=ERROR_CODES["USER_NOT_FOUND"],
        )

    profile = ProfilePublic.model_validate(matching[0]).model_dump(mode="json")

    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "profile": profile,
    }


def _gravatar_url(email: str) -> str:
    """Return the Gravatar URL for a given email address."""
    email_hash = hashlib.md5(email.strip().lower().encode()).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=200"


def _create_access_token(sub: str) -> str:
    """Create a signed JWT access token for the given subject (user UUID)."""
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_expiry_minutes)
    payload = {
        "sub": sub,
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _create_reset_token(sub: str) -> str:
    """Create a short-lived JWT with purpose='password_reset'."""
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_reset_token_expiry_minutes)
    payload = {
        "sub": sub,
        "purpose": "password_reset",
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _invalid_reset_token() -> AppException:
    return AppException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid, expired, or already used reset token",
        error_code=ERROR_CODES["TOKEN_INVALID"],
    )


def _build_frontend_reset_link(token: str) -> str:
    base_url = settings.frontend_base_url.rstrip("/")
    return f"{base_url}/reset-password?token={token}"


def _simulate_reset_email_delivery(reset_link: str) -> bool:
    """Persist a local simulated reset link without printing sensitive values."""
    try:
        outbox_path = Path("/tmp/password_reset_simulation.txt")
        outbox_path.write_text(f"{reset_link}\n", encoding="utf-8")
        return True
    except OSError:
        logger.warning("Password reset email simulation failed")
        return False


def _send_reset_email(email: str, token: str) -> None:
    reset_link = _build_frontend_reset_link(token)
    api_key = settings.resend_api_key
    if not api_key:
        if _simulate_reset_email_delivery(reset_link):
            logger.info("Password reset email simulation triggered")
        return

    resend.api_key = api_key
    try:
        resend.Emails.send(
            {
                "from": settings.resend_from_email,
                "to": [email],
                "subject": "Reset your password",
                "html": (
                    "<p>We received a request to reset your password.</p>"
                    f"<p><a href=\"{reset_link}\">Reset password</a></p>"
                    "<p>If you did not request this, you can ignore this email.</p>"
                ),
            }
        )
    except (resend.exceptions.ResendError, RequestException):
        # Keep endpoint behavior non-enumerable and resilient in local/dev setups.
        logger.warning("Password reset email delivery failed")
        if _simulate_reset_email_delivery(reset_link):
            logger.info("Password reset email simulation triggered")


def _decode_reset_token(token: str) -> tuple[str, datetime]:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise _invalid_reset_token() from None

    purpose: str | None = payload.get("purpose")
    if purpose != "password_reset":
        raise _invalid_reset_token()

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise _invalid_reset_token()

    raw_iat = payload.get("iat")
    if isinstance(raw_iat, str):
        try:
            raw_iat = float(raw_iat)
        except ValueError:
            raise _invalid_reset_token() from None
    if not isinstance(raw_iat, int | float):
        raise _invalid_reset_token()

    issued_at = datetime.fromtimestamp(raw_iat, tz=UTC)
    return user_id_str, issued_at


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: UserCreate) -> dict:
    """Register a new user account.

    Hashes the password, generates a Gravatar URL, stores the user, and
    returns the public profile (no JWT).
    """
    db = get_db()
    users_table = db.table("users")
    profiles_table = db.table("profiles")

    # Check for duplicate email
    if users_table.search(lambda doc: doc.get("email") == body.email):
        raise email_already_exists()

    hashed = pwd_context.hash(body.password)
    gravatar = _gravatar_url(body.email)
    user = User(
        email=body.email,
        hashed_password=hashed,
        gravatar_url=gravatar,
    )
    serialized = user.model_dump(mode="json")
    users_table.insert(serialized)

    profile = Profile(
        user_id=user.id,
        name=body.name,
        phone=body.phone,
        address=body.address,
    )

    profiles_table.insert(profile.model_dump(mode="json"))

    return UserPublic.model_validate(user).model_dump(mode="json")


@router.post("/login")
def login(body: UserLogin) -> dict:
    """Authenticate with email and password, receive a JWT."""
    db = get_db()
    users_table = db.table("users")

    matching = users_table.search(lambda doc: doc.get("email") == body.email)
    if not matching:
        raise invalid_credentials()

    doc = matching[0]
    user = User.model_validate(doc)

    if not user.is_active:
        raise invalid_credentials()

    if not pwd_context.verify(body.password, user.hashed_password):
        raise invalid_credentials()

    token = _create_access_token(str(user.id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserPublic.model_validate(user).model_dump(mode="json"),
    }


@router.post("/request-reset-link")
def request_reset_link(body: RequestResetLinkRequest) -> dict:
    """Request a password reset link.

    Always returns 200 regardless of whether the email exists, to prevent
    email enumeration. When the email exists, a reset link is printed to the
    backend console as a simulated email.
    """
    return forgot_password(body)


@router.post("/forgot-password")
def forgot_password(body: RequestResetLinkRequest) -> dict:
    """Request a password reset email without revealing whether user exists."""
    db = get_db()
    users_table = db.table("users")

    matching = users_table.search(lambda doc: doc.get("email") == body.email)
    if matching:
        doc = matching[0]
        user = User.model_validate(doc)
        token = _create_reset_token(str(user.id))
        _send_reset_email(body.email, token)

    return {
        "detail": "If an account with that email exists, a reset link has been sent."
    }


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest) -> dict:
    """Reset a user's password given a valid reset token.

    Validates the JWT, verifies the purpose claim, and updates the password.
    """
    user_id_str, issued_at = _decode_reset_token(body.token)

    db = get_db()
    users_table = db.table("users")

    matching = users_table.search(lambda doc: doc.get("id") == user_id_str)
    if not matching:
        # User was deleted between token issuance and use — treat as invalid
        raise _invalid_reset_token()

    user_doc = matching[0]
    user = User.model_validate(user_doc)
    if user.password_changed_at is not None and issued_at <= user.password_changed_at:
        raise _invalid_reset_token()

    now = datetime.now(UTC)
    user.hashed_password = pwd_context.hash(body.new_password)
    user.password_changed_at = now
    user.updated_at = now

    doc_id = user_doc.doc_id
    users_table.update(user.model_dump(mode="json"), doc_ids=[doc_id])

    return {"detail": "Password has been reset successfully."}


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> dict:
    """Change password for an authenticated user after current-password check."""
    db = get_db()
    users_table = db.table("users")

    matching = users_table.search(lambda doc: doc.get("id") == str(current_user.id))
    if not matching:
        raise token_invalid()

    user_doc = matching[0]
    user = User.model_validate(user_doc)
    if not pwd_context.verify(body.current_password, user.hashed_password):
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
            error_code=ERROR_CODES["INVALID_CREDENTIALS"],
        )

    now = datetime.now(UTC)
    user.hashed_password = pwd_context.hash(body.new_password)
    user.password_changed_at = now
    user.updated_at = now

    users_table.update(user.model_dump(mode="json"), doc_ids=[user_doc.doc_id])

    return {"detail": "Password updated successfully."}
