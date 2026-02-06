from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools


@pytest.fixture
async def mcp():
    mcp_instance = FastMCP("test")
    register_tools(mcp_instance)
    return mcp_instance


@pytest.mark.asyncio
async def test_get_transactions_filters_by_amount_range(mcp):
    """Verify get_transactions filters by min_amount and max_amount."""
    mock_client = AsyncMock()
    # Mock return with varied amounts
    mock_client.get_transactions.return_value = {
        "allTransactions": {
            "results": [
                {"id": "1", "amount": 10.0, "description": "Small"},
                {"id": "2", "amount": 50.0, "description": "Medium"},
                {"id": "3", "amount": 100.0, "description": "Large"},
            ]
        }
    }

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transactions")

        # Test filtering for Medium transactions
        data = await tool.fn(min_amount=40.0, max_amount=60.0)
        assert len(data) == 1
        assert data[0]["id"] == "2"


@pytest.mark.asyncio
async def test_get_transactions_filters_by_category_id(mcp):
    """Verify get_transactions passes category_id to the SDK."""
    mock_client = AsyncMock()
    mock_client.get_transactions.return_value = {"allTransactions": {"results": []}}

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transactions")

        await tool.fn(category_id="cat_123")

        # Check if SDK was called with categories list
        args, kwargs = mock_client.get_transactions.call_args
        assert "category_ids" in kwargs
        assert kwargs["category_ids"] == ["cat_123"]


@pytest.mark.asyncio
async def test_search_transactions_is_registered(mcp):
    """Verify search_transactions is registered and uses SDK search."""
    mock_client = AsyncMock()
    mock_client.get_transactions.return_value = {"allTransactions": {"results": []}}

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("search_transactions")
        await tool.fn(query="test keyword")

        args, kwargs = mock_client.get_transactions.call_args
        assert kwargs["search"] == "test keyword"


@pytest.mark.asyncio
async def test_get_transaction_stats_logic(mcp):
    """Verify get_transaction_stats correctly aggregates data."""
    mock_client = AsyncMock()
    mock_client.get_transactions.return_value = {
        "allTransactions": {
            "results": [
                {"amount": 100.0, "description": "Salary"},  # Income
                {"amount": -50.0, "description": "Groceries"},  # Expense
                {"amount": -25.0, "description": "Coffee"},  # Expense
            ]
        }
    }

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        # This will fail until implemented
        tool = await mcp._tool_manager.get_tool("get_transaction_stats")
        data = await tool.fn()
        assert data["count"] == 3
        assert data["sum_income"] == 100.0
        assert data["sum_expense"] == -75.0
        assert data["net"] == 25.0


@pytest.mark.asyncio
async def test_get_transactions_payload_is_optimized(mcp):
    """Verify get_transactions returns only essential fields."""
    mock_client = AsyncMock()
    mock_client.get_transactions.return_value = {
        "allTransactions": {
            "results": [
                {
                    "id": "1",
                    "date": "2024-01-01",
                    "amount": 10.0,
                    "description": "Test",
                    "category": {"name": "Food"},
                    "account": {"displayName": "Checking"},
                    "merchant": {"name": "Test Merchant"},
                    "isPending": False,
                    "someExtraField": "extra",  # Should be removed
                }
            ]
        }
    }

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transactions")
        data = await tool.fn()
        txn = data[0]
        # Check essential fields are there
        assert "id" in txn
        assert "date" in txn
        assert "amount" in txn
        # Check extra field is gone
        assert "someExtraField" not in txn
