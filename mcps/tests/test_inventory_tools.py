"""Inventory tool tests: read-only access, write rejection, scope enforcement."""

from __future__ import annotations

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import server

PRODUCT = {
    "id": 1,
    "name": "Classic Trench Coat",
    "sku": "MAR-TC-001",
    "client_name": "Maison Atelier Rue",
    "category": "fashion",
    "warehouse": "LA",
    "current_stock": 42,
}

ORDER = {
    "movement_type": "inbound",
    "id": 7,
    "sku_id": 1,
    "sku": "MAR-TC-001",
    "name": "Classic Trench Coat",
    "client_name": "Maison Atelier Rue",
    "warehouse": "LA",
    "quantity": 10,
    "created_at": "2026-01-01T00:00:00+00:00",
    "user_uuid": "22222222-2222-2222-2222-222222222222",
    "reference": "PO-001",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["inventory:read"]], indirect=True)
async def test_list_inventory_products(authenticated, mock_backend) -> None:
    mock_backend(lambda request: httpx.Response(200, json=[PRODUCT]))

    async with Client(server.mcp) as client:
        result = await client.call_tool("list_inventory_products", {})

    assert len(result.data) == 1
    assert result.data[0].sku == "MAR-TC-001"


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["inventory:read"]], indirect=True)
async def test_get_inventory_product(authenticated, mock_backend) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/inventory/products/1"
        return httpx.Response(200, json=PRODUCT)

    mock_backend(handler)

    async with Client(server.mcp) as client:
        result = await client.call_tool("get_inventory_product", {"product_id": 1})

    assert result.data.current_stock == 42


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["inventory:read"]], indirect=True)
async def test_get_inventory_product_not_found(authenticated, mock_backend) -> None:
    mock_backend(lambda request: httpx.Response(404, json={"detail": "SKU not found"}))

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="NOT_FOUND"):
            await client.call_tool("get_inventory_product", {"product_id": 999})


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["inventory:read"]], indirect=True)
async def test_list_inventory_orders(authenticated, mock_backend) -> None:
    mock_backend(lambda request: httpx.Response(200, json=[ORDER]))

    async with Client(server.mcp) as client:
        result = await client.call_tool("list_inventory_orders", {})

    assert result.data[0].movement_type == "inbound"


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["incidents:read"]], indirect=True)
async def test_list_inventory_products_wrong_scope(authenticated, mock_backend) -> None:
    mock_backend(lambda request: httpx.Response(200, json=[PRODUCT]))

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="Insufficient scope"):
            await client.call_tool("list_inventory_products", {})


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [["inventory:read"]], indirect=True)
async def test_reject_inventory_write_always_raises(authenticated, mock_backend) -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(201, json=PRODUCT)

    mock_backend(handler)

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="INVENTORY_READ_ONLY"):
            await client.call_tool("reject_inventory_write", {"attempted_action": "create_product"})

    # The tool must never forward the attempt to the backend.
    assert called is False


@pytest.mark.asyncio
async def test_reject_inventory_write_requires_authentication(unauthenticated, mock_backend) -> None:
    mock_backend(lambda request: httpx.Response(201, json=PRODUCT))

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="AUTHENTICATION_REQUIRED"):
            await client.call_tool("reject_inventory_write", {"attempted_action": "inbound"})
