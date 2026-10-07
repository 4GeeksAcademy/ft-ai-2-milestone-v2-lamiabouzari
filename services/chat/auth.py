"""WebSocket JWT checks using the same secret and user store as the backoffice."""

from __future__ import annotations

import uuid

from jose import JWTError, jwt

from config import settings
from models.user import User


def authenticate_token(token: str | None) -> User | None:
    """Return the user for a JWT, or None when the token is missing or invalid."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = uuid.UUID(str(user_id_str))
    except (JWTError, ValueError):
        return None

    import database

    users_table = database.get_db().table("users")
    matching = users_table.search(lambda doc: doc.get("id") == str(user_id))
    if not matching:
        return None
    return User.model_validate(matching[0])
