"""Pydantic Profile models."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class Profile(BaseModel):
    """Internal Profile representation stored in TinyDB."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class ProfileUpdate(BaseModel):
    """Request body for updating the current user's profile."""

    name: str | None = None
    phone: str | None = None
    address: str | None = None


class ProfilePublic(BaseModel):
    """Public-facing Profile response."""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str | None = None
    phone: str | None = None
    address: str | None = None