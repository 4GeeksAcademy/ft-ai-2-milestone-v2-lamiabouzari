"""FastAPI dependencies (e.g., get_current_user)."""

from __future__ import annotations

import uuid

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from config import settings
from database import get_db
from exceptions import token_invalid, token_missing_sub
from models.user import User, UserPublic

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> UserPublic:
    """Extract and validate the JWT from the Authorization header.

    Returns the public user profile of the authenticated user.
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise token_missing_sub()
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise token_invalid()

    db = get_db()
    users_table = db.table("users")

    matching = users_table.search(lambda doc: doc.get("id") == str(user_id))
    if not matching:
        raise token_invalid()

    user = User.model_validate(matching[0])
    return UserPublic.model_validate(user)