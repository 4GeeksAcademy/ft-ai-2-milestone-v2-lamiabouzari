"""Supplier directory routes on the existing FastAPI application."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from api.repository import create_supplier, delete_supplier, get_supplier, list_suppliers, update_rate, update_status
from api.schemas import Category, Country, RateUpdate, StatusUpdate, SupplierCreate
from dependencies import get_current_user
from exceptions import AppException
from models.user import UserPublic

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _missing() -> AppException:
    return AppException(status.HTTP_404_NOT_FOUND, "Supplier not found.", "SUPPLIER_NOT_FOUND")


@router.post("", status_code=status.HTTP_201_CREATED)
def post_supplier(
    body: SupplierCreate,
    _user: UserPublic = Depends(get_current_user),
) -> dict:
    return create_supplier(body)


@router.get("")
def get_suppliers(
    country: Country | None = None,
    category: Category | None = None,
    _user: UserPublic = Depends(get_current_user),
) -> list[dict]:
    return list_suppliers(country=country, category=category)


@router.get("/{supplier_id}")
def get_supplier_detail(
    supplier_id: int,
    _user: UserPublic = Depends(get_current_user),
) -> dict:
    supplier = get_supplier(supplier_id)
    if supplier is None:
        raise _missing()
    return supplier


@router.patch("/{supplier_id}/rate")
def patch_supplier_rate(
    supplier_id: int,
    body: RateUpdate,
    _user: UserPublic = Depends(get_current_user),
) -> dict:
    supplier = update_rate(supplier_id, body.rate_per_shipment)
    if supplier is None:
        raise _missing()
    return supplier


@router.patch("/{supplier_id}/status")
def patch_supplier_status(
    supplier_id: int,
    body: StatusUpdate,
    _user: UserPublic = Depends(get_current_user),
) -> dict:
    supplier = update_status(supplier_id, body.status)
    if supplier is None:
        raise _missing()
    return supplier


@router.delete("/{supplier_id}")
def delete_supplier_record(
    supplier_id: int,
    _user: UserPublic = Depends(get_current_user),
) -> dict:
    if not delete_supplier(supplier_id):
        raise _missing()
    return {"id": supplier_id, "detail": "Supplier deleted."}
