"""User management router — GET /user/{id}, PATCH /user/{id}."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from passlib.context import CryptContext

from database import get_db
from dependencies import get_current_user
from exceptions import (
    forbidden,
    invalid_user_id,
    password_too_long,
    user_not_found,
)
from models.user import User, UserCreate, UserPublic, UserRole, UserUpdate
from routers.auth import register as register_user

router = APIRouter(prefix="/users", tags=["users"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate) -> dict:
    """Create a new user by reusing the existing registration behavior."""
    return register_user(body)


def _parse_user_id(raw: str) -> uuid.UUID:
    """Parse a UUID from a string, raising invalid_user_id on failure."""
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise invalid_user_id() from None


def _find_user_by_uuid(users_table, user_uuid: uuid.UUID) -> tuple[User, int]:
    """Find a user by UUID. Returns (User, doc_id) or raises user_not_found."""
    matching = users_table.search(
        lambda doc: doc.get("id") == str(user_uuid)
    )
    if not matching:
        raise user_not_found()
    doc = matching[0]
    user = User.model_validate(doc)
    return user, doc.doc_id

@router.get("", response_model=list[UserPublic])
def list_users(
    _current_user: UserPublic = Depends(get_current_user),
) -> list[UserPublic]:
    """Return all users. Authentication required."""
    db = get_db()
    users_table = db.table("users")

    return [
        UserPublic.model_validate(
            {
                **user,
                "is_active": user.get("is_active", True),
                "role": user.get("role", UserRole.user),
            }
        )
        for user in users_table.all()
    ]

@router.get("/{user_id}", response_model=UserPublic)
def get_user(
    user_id: str,
    _current_user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    """Return a user's public profile by UUID. Authentication required."""
    db = get_db()
    users_table = db.table("users")

    user_uuid = _parse_user_id(user_id)
    user, _doc_id = _find_user_by_uuid(users_table, user_uuid)

    return UserPublic.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> None:
    """Delete a user account. Admins may delete any user; users may delete themselves."""
    db = get_db()
    users_table = db.table("users")
    profiles_table = db.table("profiles")

    user_uuid = _parse_user_id(user_id)

    is_admin = current_user.role == UserRole.admin
    if current_user.id != user_uuid and not is_admin:
        raise forbidden()

    _user, doc_id = _find_user_by_uuid(users_table, user_uuid)
    users_table.remove(doc_ids=[doc_id])
    profiles_table.remove(lambda doc: doc.get("user_id") == str(user_uuid))


@router.put("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: str,
    body: UserUpdate,
    current_user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    """Update a user's profile. The requester must be the target user."""
    db = get_db()
    users_table = db.table("users")

    user_uuid = _parse_user_id(user_id)

    # Users may update themselves; admins may update any user.
    is_admin = current_user.role == UserRole.admin

    if current_user.id != user_uuid and not is_admin:
      raise forbidden()

    user, doc_id = _find_user_by_uuid(users_table, user_uuid)
    update_data = body.model_dump(exclude_unset=True)
    if "role" in update_data:
      if not is_admin:
        raise forbidden()
      user.role = update_data["role"]

    if "email" in update_data:
        user.email = update_data["email"]
        user.gravatar_url = _gravatar_url(update_data["email"])
    if "password" in update_data:
        if len(update_data["password"]) > 128:
            raise password_too_long()
        user.hashed_password = pwd_context.hash(update_data["password"])
    if "gravatar_url" in update_data:
        user.gravatar_url = update_data["gravatar_url"]

    user.updated_at = datetime.now(UTC)
    serialized = user.model_dump(mode="json")
    users_table.update(serialized, doc_ids=[doc_id])

    return UserPublic.model_validate(user)


def _gravatar_url(email: str) -> str:
    """Return the Gravatar URL for a given email address."""
    import hashlib
    email_hash = hashlib.md5(email.strip().lower().encode()).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=200"