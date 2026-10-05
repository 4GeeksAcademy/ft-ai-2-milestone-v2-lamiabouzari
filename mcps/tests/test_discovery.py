"""Tool discovery / registration tests."""

from __future__ import annotations

import pytest
from fastmcp import Client

import server


@pytest.mark.asyncio
async def test_all_expected_tools_are_registered() -> None:
    async with Client(server.mcp) as client:
        tools = await client.list_tools()

    names = {tool.name for tool in tools}
    assert names == {
        "get_incident",
        "create_incident",
        "update_incident_status",
        "list_inventory_products",
        "get_inventory_product",
        "list_inventory_orders",
        "reject_inventory_write",
    }


@pytest.mark.asyncio
async def test_tools_have_descriptions_and_schemas() -> None:
    async with Client(server.mcp) as client:
        tools = await client.list_tools()

    by_name = {tool.name: tool for tool in tools}

    incident_tool = by_name["get_incident"]
    assert incident_tool.description
    assert "incident_id" in incident_tool.input_schema["properties"]

    create_tool = by_name["create_incident"]
    for field in ("title", "description", "category", "origin", "branch"):
        assert field in create_tool.input_schema["properties"]

    reject_tool = by_name["reject_inventory_write"]
    assert "read-only" in reject_tool.description.lower()
