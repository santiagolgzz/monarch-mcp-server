"""Tests for budget management tools."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.mark.asyncio
async def test_get_budgets_success(mcp):
    """Verify get_budgets returns formatted budget list."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_budgets.return_value = {
        "budgets": [
            {
                "id": "bud_1",
                "name": "Groceries",
                "amount": 500.0,
                "spent": 150.0,
                "remaining": 350.0,
                "category": {"name": "Food & Dining"},
                "period": "monthly",
            },
            {
                "id": "bud_2",
                "name": "Entertainment",
                "amount": 200.0,
                "spent": 50.0,
                "remaining": 150.0,
                "category": {"name": "Entertainment"},
                "period": "monthly",
            },
        ]
    }

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_budgets")
        data = await tool.fn()
        assert len(data) == 2
        assert data[0]["id"] == "bud_1"
        assert data[0]["name"] == "Groceries"
        assert data[0]["amount"] == 500.0
        assert data[0]["spent"] == 150.0
        assert data[0]["remaining"] == 350.0
        assert data[0]["category"] == "Food & Dining"
        assert data[0]["period"] == "monthly"


@pytest.mark.asyncio
async def test_get_budgets_empty_list(mcp):
    """Verify get_budgets handles empty budget list."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_budgets.return_value = {"budgets": []}

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_budgets")
        data = await tool.fn()
        assert data == []


@pytest.mark.asyncio
async def test_get_budgets_missing_category(mcp):
    """Verify get_budgets handles budgets without category."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_budgets.return_value = {
        "budgets": [
            {
                "id": "bud_1",
                "name": "Miscellaneous",
                "amount": 100.0,
                "spent": 25.0,
                "remaining": 75.0,
                "category": {},  # Empty category dict (missing name)
                "period": "monthly",
            }
        ]
    }

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_budgets")
        data = await tool.fn()
        assert len(data) == 1
        assert data[0]["category"] is None  # Empty dict returns None for name


@pytest.mark.asyncio
async def test_get_budgets_missing_budgets_key(mcp):
    """Verify get_budgets handles missing budgets key in response."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_budgets.return_value = {}  # No budgets key

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_budgets")
        data = await tool.fn()
        assert data == []


@pytest.mark.asyncio
async def test_set_budget_amount_success(mcp):
    """Verify set_budget_amount calls SDK with correct parameters."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.set_budget_amount.return_value = {
        "success": True,
        "category_id": "cat_123",
        "amount": 750.0,
    }

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        # Also mock safety guard - must return (True, None) tuple
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("set_budget_amount")
            data = await tool.fn(category_id="cat_123", amount=750.0)
            assert data["success"] is True
            mock_client.set_budget_amount.assert_called_once_with(
                amount=750.0, category_id="cat_123"
            )


@pytest.mark.asyncio
async def test_get_budgets_partial_data(mcp):
    """Verify get_budgets handles budgets with missing optional fields."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_budgets.return_value = {
        "budgets": [
            {
                "id": "bud_1",
                # Missing name, amount, spent, remaining
                "category": {"name": "Test"},
            }
        ]
    }

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_budgets")
        data = await tool.fn()
        assert len(data) == 1
        assert data[0]["id"] == "bud_1"
        assert data[0]["name"] is None
        assert data[0]["amount"] is None
        assert data[0]["category"] == "Test"
