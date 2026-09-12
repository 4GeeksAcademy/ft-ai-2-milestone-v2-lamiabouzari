"""Inventory domain: SQLModel tables (Postgres) and API schemas.

Preserves the field names and business rules from the Milestone 5 Part 1
reference implementation. Stored in Postgres via SQLModel, separate from the
TinyDB-backed user/auth database used elsewhere in this service.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

Warehouse = Literal["LA", "ZGZ"]
Category = Literal["fashion", "electronics", "cosmetics"]
ExitType = Literal["dispatch", "loss"]


# ---------------------------------------------------------------------------
# SQLModel tables (Postgres)
# ---------------------------------------------------------------------------


class SKU(SQLModel, table=True):
    """Inventory SKU stored in a specific warehouse."""

    __tablename__ = "skus"

    id: int | None = SQLField(default=None, primary_key=True)
    name: str
    sku: str
    client_name: str
    category: str
    warehouse: str


class StockEntry(SQLModel, table=True):
    """Inbound stock movement for a SKU."""

    __tablename__ = "stock_entries"

    id: int | None = SQLField(default=None, primary_key=True)
    sku_id: int = SQLField(foreign_key="skus.id")
    quantity: int
    reference: str
    warehouse: str
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC))
    user_uuid: UUID


class StockExit(SQLModel, table=True):
    """Outbound stock movement for a SKU."""

    __tablename__ = "stock_exits"

    id: int | None = SQLField(default=None, primary_key=True)
    sku_id: int = SQLField(foreign_key="skus.id")
    quantity: int
    exit_type: str
    tracking_number: str | None = None
    warehouse: str
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC))
    user_uuid: UUID


# ---------------------------------------------------------------------------
# API schemas (request/response)
# ---------------------------------------------------------------------------


class SKUCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    sku: str
    client_name: str
    category: Category
    warehouse: Warehouse


class SKUResponse(SKUCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    current_stock: int


class StockEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: int
    quantity: int = Field(gt=0)
    reference: str
    warehouse: Warehouse


class StockEntryResponse(StockEntryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    user_uuid: UUID


class StockExitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: int
    quantity: int = Field(gt=0)
    exit_type: ExitType
    tracking_number: str | None = None
    warehouse: Warehouse


class StockExitResponse(StockExitCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    user_uuid: UUID


class OrderResponse(BaseModel):
    """Unified representation of an inbound or outbound movement."""

    movement_type: Literal["inbound", "outbound"]
    id: int
    sku_id: int
    sku: str
    name: str
    client_name: str
    warehouse: Warehouse
    quantity: int
    created_at: datetime
    user_uuid: UUID
    reference: str | None = None
    exit_type: ExitType | None = None
    tracking_number: str | None = None
