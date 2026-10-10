"""Input and response schemas for the TrackFlow supplier directory.

Field names, categories, statuses, and the currency rule come from
CONTEXT-company.md. Clients cannot supply updated_at.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Country = Literal["USA", "Spain"]
Currency = Literal["USD", "EUR"]
Status = Literal["active", "suspended"]
Category = Literal[
    "carrier_last_mile",
    "carrier_international",
    "warehouse_supplies",
    "packaging_materials",
    "reverse_logistics",
    "fleet_maintenance",
    "it_and_wms_software",
    "cleaning_and_facilities",
]

VALID_CATEGORIES: tuple[str, ...] = (
    "carrier_last_mile",
    "carrier_international",
    "warehouse_supplies",
    "packaging_materials",
    "reverse_logistics",
    "fleet_maintenance",
    "it_and_wms_software",
    "cleaning_and_facilities",
)
VALID_STATUSES: tuple[str, ...] = ("active", "suspended")
COUNTRY_CURRENCY = {"USA": "USD", "Spain": "EUR"}


def _blank_to_none(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _positive_rate(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("must be a finite number greater than 0")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("must be a finite number greater than 0")
    return number


class SupplierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    country: Country
    categories: list[Category] = Field(min_length=1)
    rate_per_shipment: float
    currency: Currency
    status: Status
    service_zone: str | None = None
    contact_email: EmailStr | None = None
    notes: str | None = None

    @field_validator("rate_per_shipment")
    @classmethod
    def rate_is_positive(cls, value: object) -> float:
        return _positive_rate(value)

    @field_validator("service_zone", "notes", "contact_email", mode="before")
    @classmethod
    def empty_optional(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("categories")
    @classmethod
    def categories_are_unique(cls, value: list[Category]) -> list[Category]:
        if len(value) != len(set(value)):
            raise ValueError("categories must not contain duplicates")
        return value

    @model_validator(mode="after")
    def currency_matches_country(self) -> "SupplierCreate":
        expected = COUNTRY_CURRENCY[self.country]
        if self.currency != expected:
            raise ValueError(f"{self.country} suppliers must use {expected}")
        return self


class RateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate_per_shipment: float

    @field_validator("rate_per_shipment")
    @classmethod
    def rate_is_positive(cls, value: object) -> float:
        return _positive_rate(value)


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status


class SupplierResponse(BaseModel):
    id: int
    name: str
    country: Country
    categories: list[Category]
    rate_per_shipment: float
    currency: Currency
    updated_at: datetime
    status: Status
    service_zone: str | None = None
    contact_email: str | None = None
    notes: str | None = None
