"""Inventory management endpoints backed by Postgres (SQLModel).

Business rules preserved from the Milestone 5 Part 1 reference implementation:
warehouse-matching, dispatch/loss tracking-number rules, insufficient-stock
checks, and audit fields (``user_uuid``) on every stock movement.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlmodel import Session, select

from database import get_inventory_db
from dependencies import get_current_user
from exceptions import AppException
from models.inventory import (
    SKU,
    OrderResponse,
    SKUCreate,
    SKUResponse,
    StockEntry,
    StockEntryCreate,
    StockEntryResponse,
    StockExit,
    StockExitCreate,
    StockExitResponse,
)
from models.user import UserPublic

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _bad_request(detail: str) -> AppException:
    return AppException(400, detail, "VALIDATION_ERROR")


def _current_stock(session: Session, sku_id: int, warehouse: str) -> int:
    entries = session.exec(
        select(func.coalesce(func.sum(StockEntry.quantity), 0)).where(
            StockEntry.sku_id == sku_id,
            StockEntry.warehouse == warehouse,
        )
    ).one()
    exits = session.exec(
        select(func.coalesce(func.sum(StockExit.quantity), 0)).where(
            StockExit.sku_id == sku_id,
            StockExit.warehouse == warehouse,
        )
    ).one()
    return int(entries or 0) - int(exits or 0)


def _sku_response(session: Session, sku: SKU) -> SKUResponse:
    return SKUResponse.model_validate(
        {**sku.model_dump(), "current_stock": _current_stock(session, sku.id, sku.warehouse)}
    )


@router.get("/products", response_model=list[SKUResponse])
def list_products(session: Session = Depends(get_inventory_db)) -> list[SKUResponse]:
    products = session.exec(select(SKU).order_by(SKU.id)).all()
    return [_sku_response(session, product) for product in products]


@router.post("/products", response_model=SKUResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    body: SKUCreate,
    session: Session = Depends(get_inventory_db),
) -> SKUResponse:
    product = SKU(**body.model_dump())
    session.add(product)
    session.commit()
    session.refresh(product)
    return _sku_response(session, product)


@router.get("/products/{product_id}", response_model=SKUResponse)
def get_product(product_id: int, session: Session = Depends(get_inventory_db)) -> SKUResponse:
    product = session.get(SKU, product_id)
    if product is None:
        raise AppException(404, "SKU not found", "NOT_FOUND")
    return _sku_response(session, product)


@router.post(
    "/orders/inbound",
    response_model=StockEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_inbound(
    body: StockEntryCreate,
    current_user: UserPublic = Depends(get_current_user),
    session: Session = Depends(get_inventory_db),
) -> StockEntryResponse:
    product = session.get(SKU, body.sku_id)
    if product is None:
        raise AppException(404, "SKU not found", "NOT_FOUND")
    if body.warehouse != product.warehouse:
        raise _bad_request("Movement warehouse must match the SKU warehouse.")

    entry = StockEntry(**body.model_dump(), user_uuid=current_user.id)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return StockEntryResponse.model_validate(entry)


@router.post(
    "/orders/outbound",
    response_model=StockExitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_outbound(
    body: StockExitCreate,
    current_user: UserPublic = Depends(get_current_user),
    session: Session = Depends(get_inventory_db),
) -> StockExitResponse:
    product = session.get(SKU, body.sku_id)
    if product is None:
        raise AppException(404, "SKU not found", "NOT_FOUND")
    if body.warehouse != product.warehouse:
        raise _bad_request("Movement warehouse must match the SKU warehouse.")
    if body.exit_type == "dispatch" and not body.tracking_number:
        raise _bad_request("Tracking number is required for dispatch exits.")
    if body.exit_type == "loss" and body.tracking_number is not None:
        raise _bad_request("Tracking number must be null for loss exits.")

    available = _current_stock(session, product.id, product.warehouse)
    if available < body.quantity:
        raise _bad_request(
            f"Insufficient stock for SKU '{product.sku}'. "
            f"Available: {available}, requested: {body.quantity}."
        )

    stock_exit = StockExit(**body.model_dump(), user_uuid=current_user.id)
    session.add(stock_exit)
    session.commit()
    session.refresh(stock_exit)
    return StockExitResponse.model_validate(stock_exit)


@router.get("/orders", response_model=list[OrderResponse])
def list_orders(session: Session = Depends(get_inventory_db)) -> list[OrderResponse]:
    inbound_rows = session.exec(select(StockEntry, SKU).join(SKU, StockEntry.sku_id == SKU.id)).all()
    outbound_rows = session.exec(select(StockExit, SKU).join(SKU, StockExit.sku_id == SKU.id)).all()

    orders: list[OrderResponse] = []
    for entry, product in inbound_rows:
        orders.append(
            OrderResponse(
                movement_type="inbound",
                id=entry.id,
                sku_id=entry.sku_id,
                sku=product.sku,
                name=product.name,
                client_name=product.client_name,
                warehouse=entry.warehouse,
                quantity=entry.quantity,
                created_at=entry.created_at,
                user_uuid=entry.user_uuid,
                reference=entry.reference,
            )
        )
    for stock_exit, product in outbound_rows:
        orders.append(
            OrderResponse(
                movement_type="outbound",
                id=stock_exit.id,
                sku_id=stock_exit.sku_id,
                sku=product.sku,
                name=product.name,
                client_name=product.client_name,
                warehouse=stock_exit.warehouse,
                quantity=stock_exit.quantity,
                created_at=stock_exit.created_at,
                user_uuid=stock_exit.user_uuid,
                exit_type=stock_exit.exit_type,
                tracking_number=stock_exit.tracking_number,
            )
        )
    return sorted(orders, key=lambda order: order.created_at, reverse=True)
