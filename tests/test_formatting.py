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
async def test_get_accounts_formats_response(mcp):
    """Test that get_accounts properly formats the response."""
    mock_client = AsyncMock()
    mock_client.get_accounts.return_value = {
        "accounts": [
            {
                "id": "123",
                "displayName": "Checking",
                "type": {"name": "checking"},
                "currentBalance": 1000.50,
                "institution": {"name": "Bank of America"},
                "isActive": True,
            }
        ]
    }

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_accounts")
        data = await tool.fn()
        assert isinstance(data, list)
        assert data[0]["name"] == "Checking"
        assert data[0]["balance"] == 1000.50
        assert data[0]["institution"] == "Bank of America"


@pytest.mark.asyncio
async def test_get_transactions_formats_response(mcp):
    """Test that get_transactions properly formats the response."""
    mock_client = AsyncMock()
    mock_client.get_transactions.return_value = {
        "allTransactions": {
            "results": [
                {
                    "id": "txn_123",
                    "date": "2024-01-15",
                    "amount": -50.25,
                    "description": "Grocery Store",
                    "category": {"name": "Food"},
                    "account": {"displayName": "Checking"},
                    "merchant": {"name": "Whole Foods"},
                }
            ]
        }
    }

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transactions")
        data = await tool.fn(limit=1)
        assert isinstance(data, list)
        assert data[0]["description"] == "Grocery Store"
        assert data[0]["amount"] == -50.25
        assert data[0]["category"] == "Food"
