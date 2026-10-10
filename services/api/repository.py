"""TinyDB access for the suppliers table only."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tinydb.table import Document

from api.schemas import SupplierCreate, SupplierResponse
from database import get_db

SUPPLIERS_TABLE = "suppliers"


def suppliers_table():
    return get_db().table(SUPPLIERS_TABLE)


def natural_key(name: str, country: str) -> str:
    return f"{name.strip().casefold()}|{country.strip()}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _public(document: Document) -> dict[str, Any]:
    payload = {
        "id": document.doc_id,
        "name": document["name"],
        "country": document["country"],
        "categories": list(document["categories"]),
        "rate_per_shipment": document["rate_per_shipment"],
        "currency": document["currency"],
        "updated_at": document["updated_at"],
        "status": document["status"],
        "service_zone": document.get("service_zone"),
        "contact_email": document.get("contact_email"),
        "notes": document.get("notes"),
    }
    return SupplierResponse.model_validate(payload).model_dump(mode="json")


def _stored(supplier: SupplierCreate, updated_at: str) -> dict[str, Any]:
    return {
        "name": supplier.name,
        "country": supplier.country,
        "categories": list(supplier.categories),
        "rate_per_shipment": supplier.rate_per_shipment,
        "currency": supplier.currency,
        "updated_at": updated_at,
        "status": supplier.status,
        "service_zone": supplier.service_zone,
        "contact_email": str(supplier.contact_email) if supplier.contact_email else None,
        "notes": supplier.notes,
    }


def list_suppliers(country: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for document in suppliers_table().all():
        if country and document.get("country") != country:
            continue
        if category and category not in (document.get("categories") or []):
            continue
        rows.append(_public(document))
    rows.sort(key=lambda row: row["id"])
    return rows


def get_supplier(supplier_id: int) -> dict[str, Any] | None:
    document = suppliers_table().get(doc_id=supplier_id)
    if document is None:
        return None
    return _public(document)


def create_supplier(supplier: SupplierCreate) -> dict[str, Any]:
    document_id = suppliers_table().insert(_stored(supplier, _now()))
    created = get_supplier(document_id)
    if created is None:
        raise RuntimeError("Supplier was not stored.")
    return created


def update_rate(supplier_id: int, rate_per_shipment: float) -> dict[str, Any] | None:
    table = suppliers_table()
    if table.get(doc_id=supplier_id) is None:
        return None
    table.update(
        {"rate_per_shipment": rate_per_shipment, "updated_at": _now()},
        doc_ids=[supplier_id],
    )
    return get_supplier(supplier_id)


def update_status(supplier_id: int, status: str) -> dict[str, Any] | None:
    table = suppliers_table()
    if table.get(doc_id=supplier_id) is None:
        return None
    table.update({"status": status}, doc_ids=[supplier_id])
    return get_supplier(supplier_id)


def delete_supplier(supplier_id: int) -> bool:
    table = suppliers_table()
    if table.get(doc_id=supplier_id) is None:
        return False
    table.remove(doc_ids=[supplier_id])
    return True


def existing_keys() -> set[str]:
    return {
        natural_key(document["name"], document["country"])
        for document in suppliers_table().all()
        if document.get("name") and document.get("country")
    }
