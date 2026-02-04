import json
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.mark.asyncio
async def test_update_transaction_parameters(mcp):
    """Verify update_transaction only passes non-None parameters to the SDK."""
    register_tools(mcp)

    mock_client = AsyncMock()
    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("update_transaction")

        # Test updating only amount
        await tool.fn(transaction_id="txn_1", amount=50.0)

        # Check call arguments
        # Should NOT include merchant_name, category_id, or date if they were None
        args, kwargs = mock_client.update_transaction.call_args
        assert kwargs["transaction_id"] == "txn_1"
        assert kwargs["amount"] == 50.0
        assert "merchant_name" not in kwargs
        assert "category_id" not in kwargs
        assert "date" not in kwargs


@pytest.mark.asyncio
async def test_get_transactions_async(mcp):
    """Verify get_transactions is registered and works asynchronously."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transactions.return_value = {"allTransactions": {"results": []}}

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transactions")
        result = await tool.fn()

        data = json.loads(result)
        assert data == []
