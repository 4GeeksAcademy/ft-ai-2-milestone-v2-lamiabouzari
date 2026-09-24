"""Centralized incident domain models and mappings."""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from incident_analysis import VALID_CATEGORIES

CSV_STATUS_MAP = {"OPEN": "open", "CLOSED": "resolved", "DISCARDED": "discarded"}
CSV_BRANCH_MAP = {"US": "los_angeles", "ES": "zaragoza"}
CATEGORY_MAP = {value: value.lower() for value in VALID_CATEGORIES}
STATUSES = ("open", "in_progress", "resolved", "discarded")
ORIGINS = ("customer", "branch", "internal")
BRANCHES = ("los_angeles", "zaragoza", "central")
CATEGORIES = tuple(sorted(CATEGORY_MAP.values()))

class IncidentStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISCARDED = "discarded"

class IncidentOrigin(StrEnum):
    CUSTOMER = "customer"
    BRANCH = "branch"
    INTERNAL = "internal"

class IncidentFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category: str
    status: IncidentStatus = IncidentStatus.OPEN
    origin: IncidentOrigin
    branch: str

    @field_validator("title", "description", "category", "branch", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("category")
    @classmethod
    def valid_category(cls, value: str) -> str:
        if value not in CATEGORIES:
            raise ValueError("Invalid category")
        return value

    @field_validator("branch")
    @classmethod
    def valid_branch(cls, value: str) -> str:
        if value not in BRANCHES:
            raise ValueError("Invalid branch")
        return value

class Incident(IncidentFields):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class IncidentCreate(IncidentFields):
    pass

class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: IncidentStatus

class IncidentSummary(BaseModel):
    status: dict[str, int]
    category: dict[str, int]
    origin: dict[str, int]
    branch: dict[str, int]
