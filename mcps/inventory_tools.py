"""Inventory MCP tools — strictly READ-ONLY access to the real TrackFlow API.

Only `GET /inventory/products`, `GET /inventory/products/{id}`, and
`GET /inventory/orders` are ever called. MCP never calls
`POST /inventory/products`, `/inventory/orders/inbound`, or
`/inventory/orders/outbound` — `reject_inventory_write` exists specifically
to turn any write attempt into an explicit, structured authorization error
instead of silently doing nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, Field

from auth import require_scope
from backend_client import request_json
from errors import InventoryReadOnlyError
from logging_config import log_tool_invocation

if TYPE_CHECKING:
    from fastmcp import FastMCP

INVENTORY_READ_SCOPE = "inventory:read"


class InventoryProduct(BaseModel):
    """Structured SKU payload mirroring `services.models.inventory.SKUResponse`."""

    id: int
    name: str
    sku: str
    client_name: str
    category: str
    warehouse: str
    current_stock: int


class InventoryOrder(BaseModel):
    """Structured movement payload mirroring `services.models.inventory.OrderResponse`."""

    movement_type: str
    id: int
    sku_id: int
    sku: str
    name: str
    client_name: str
    warehouse: str
    quantity: int
    created_at: str
    user_uuid: str
    reference: str | None = None
    exit_type: str | None = None
    tracking_number: str | None = None


def register(mcp: "FastMCP") -> None:
    """Register inventory tools on the given FastMCP server instance."""

    @mcp.tool(
        name="list_inventory_products",
        description=(
            "List all TrackFlow inventory SKUs via GET /inventory/products. "
            "Read-only. Requires the 'inventory:read' scope."
        ),
        run_in_thread=False,
    )
    async def list_inventory_products() -> list[InventoryProduct]:
        auth_info = require_scope(INVENTORY_READ_SCOPE)
        with log_tool_invocation("list_inventory_products", auth_info.subject):
            data: list[dict[str, Any]] = await request_json("GET", "/inventory/products")
            return [InventoryProduct.model_validate(item) for item in data]

    @mcp.tool(
        name="get_inventory_product",
        description=(
            "Fetch one TrackFlow inventory SKU by ID via GET /inventory/products/{product_id}. "
            "Read-only. Requires the 'inventory:read' scope."
        ),
        run_in_thread=False,
    )
    async def get_inventory_product(
        product_id: Annotated[int, Field(description="Numeric SKU id.")],
    ) -> InventoryProduct:
        auth_info = require_scope(INVENTORY_READ_SCOPE)
        with log_tool_invocation("get_inventory_product", auth_info.subject):
            data = await request_json("GET", f"/inventory/products/{product_id}")
            return InventoryProduct.model_validate(data)

    @mcp.tool(
        name="list_inventory_orders",
        description=(
            "List TrackFlow inbound/outbound stock movements via GET /inventory/orders. "
            "Read-only. Requires the 'inventory:read' scope."
        ),
        run_in_thread=False,
    )
    async def list_inventory_orders() -> list[InventoryOrder]:
        auth_info = require_scope(INVENTORY_READ_SCOPE)
        with log_tool_invocation("list_inventory_orders", auth_info.subject):
            data = await request_json("GET", "/inventory/orders")
            return [InventoryOrder.model_validate(item) for item in data]

    @mcp.tool(
        name="reject_inventory_write",
        description=(
            "Always rejects inventory modification attempts. Inventory access through MCP "
            "is strictly read-only by design: SKU creation and inbound/outbound stock "
            "movements must be performed through the TrackFlow backoffice application, "
            "never through this MCP server. Calling this tool always raises a structured "
            "'INVENTORY_READ_ONLY' authorization error."
        ),
        run_in_thread=False,
    )
    async def reject_inventory_write(
        attempted_action: Annotated[
            str,
            Field(
                description=(
                    "The write action that was attempted, e.g. 'create_product', "
                    "'inbound', or 'outbound'."
                )
            ),
        ] = "unknown",
    ) -> None:
        auth_info = require_scope(INVENTORY_READ_SCOPE)
        with log_tool_invocation("reject_inventory_write", auth_info.subject):
            raise InventoryReadOnlyError(
                f"Inventory modification ('{attempted_action}') is prohibited through MCP. "
                "Inventory access is read-only by design; use the TrackFlow backoffice "
                "application instead."
            )
