"""Pydantic User model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from exceptions import password_too_long


class UserRole(str, Enum):
    admin = "admin"
    manager = "manager"
    user = "user"

class UserCreate(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=100)
    name: str | None = None
    phone: str | None = None
    address: str | None = None

    @field_validator("password")
    @classmethod
    def password_max_length(cls, v: str) -> str:
        if len(v) > 128:
            raise password_too_long()
        return v


class UserLogin(BaseModel):
    """Request body for user login."""

    email: EmailStr
    password: str


class User(BaseModel):
    """Internal User representation stored in TinyDB."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    email: EmailStr
    hashed_password: str = Field(
        validation_alias=AliasChoices("hashed_password", "password")
    )
    gravatar_url: str
    is_active: bool = True
    role: UserRole = UserRole.user
    password_changed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserPublic(BaseModel):
    """Public-facing User response (never exposes password)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str | None = None
    gravatar_url: str
    is_active: bool
    role: UserRole


class RequestResetLinkRequest(BaseModel):
    """Request body for POST /auth/request-reset-link."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request body for POST /auth/reset-password."""
    token: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_max_length(cls, v: str) -> str:
        if len(v) > 128:
            raise password_too_long()
        return v


class ChangePasswordRequest(BaseModel):
    """Request body for POST /auth/change-password."""

    current_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_max_length(cls, v: str) -> str:
        if len(v) > 128:
            raise password_too_long()
        return v


class UserUpdate(BaseModel):
    """Request body for updating a user (all fields optional)."""

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    gravatar_url: str | None = None
    role: UserRole | None = None

    @field_validator("password")
    @classmethod
    def password_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 128:
            raise password_too_long()
        return v