import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.mark.asyncio
async def test_create_transaction_success(mcp):
    """Verify create_transaction successfully creates a transaction."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.create_transaction.return_value = {
        "id": "txn_new_123",
        "date": "2024-01-15",
        "amount": -50.0,
        "merchant": {"name": "Test Merchant"},
        "category": {"id": "cat_123", "name": "Food"},
        "account": {"id": "acc_123", "displayName": "Checking"},
    }

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, "OK")
            mock_guard.return_value.record_operation = MagicMock()

            tool = await mcp._tool_manager.get_tool("create_transaction")
            result = await tool.fn(
                account_id="acc_123",
                amount=-50.0,
                merchant_name="Test Merchant",
                category_id="cat_123",
                date="2024-01-15",
            )

            data = json.loads(result)
            assert data["id"] == "txn_new_123"
            assert data["amount"] == -50.0

            # Verify SDK was called
            mock_client.create_transaction.assert_called_once()


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


@pytest.mark.asyncio
async def test_get_transactions_null_category(mcp):
    """Verify get_transactions handles null category."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transactions.return_value = {
        "allTransactions": {
            "results": [
                {
                    "id": "txn_1",
                    "date": "2024-01-15",
                    "amount": -50.0,
                    "description": "Unknown",
                    "category": None,  # No category
                    "account": {"displayName": "Checking"},
                    "merchant": {"name": "Store"},
                    "isPending": False,
                }
            ]
        }
    }

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transactions")
        result = await tool.fn()

        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["category"] is None


@pytest.mark.asyncio
async def test_get_transactions_null_merchant(mcp):
    """Verify get_transactions handles null merchant."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transactions.return_value = {
        "allTransactions": {
            "results": [
                {
                    "id": "txn_1",
                    "date": "2024-01-15",
                    "amount": -50.0,
                    "description": "Transfer",
                    "category": {"name": "Transfer"},
                    "account": {"displayName": "Checking"},
                    "merchant": None,  # No merchant
                    "isPending": False,
                }
            ]
        }
    }

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transactions")
        result = await tool.fn()

        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["merchant"] is None


@pytest.mark.asyncio
async def test_amount_filtering_with_none(mcp):
    """Verify get_transactions handles amount filtering when amount is None."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transactions.return_value = {
        "allTransactions": {
            "results": [
                {
                    "id": "txn_1",
                    "date": "2024-01-15",
                    "amount": None,  # Some transactions may have no amount
                    "description": "Pending",
                    "category": {"name": "Other"},
                    "account": {"displayName": "Checking"},
                },
                {
                    "id": "txn_2",
                    "date": "2024-01-16",
                    "amount": -100.0,
                    "description": "Purchase",
                    "category": {"name": "Shopping"},
                    "account": {"displayName": "Checking"},
                },
            ]
        }
    }

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transactions")
        # Filter with min_amount - should skip txn_1 with None amount
        result = await tool.fn(min_amount=-150.0)

        data = json.loads(result)
        # Should include both - None amount skips the filter check
        assert len(data) == 2


@pytest.mark.asyncio
async def test_transaction_stats_empty(mcp):
    """Verify get_transaction_stats handles empty results."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transactions.return_value = {"allTransactions": {"results": []}}

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transaction_stats")
        result = await tool.fn()

        data = json.loads(result)
        assert data["count"] == 0
        assert data["sum_income"] == 0
        assert data["sum_expense"] == 0
        assert data["net"] == 0


@pytest.mark.asyncio
async def test_delete_transaction_bool_result(mcp):
    """Verify delete_transaction wraps bool result in dict."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.delete_transaction.return_value = True  # SDK returns bool

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("delete_transaction")
            result = await tool.fn(transaction_id="txn_to_delete")

            data = json.loads(result)
            assert data["deleted"] is True
            assert data["transaction_id"] == "txn_to_delete"


@pytest.mark.asyncio
async def test_update_splits_invalid_json(mcp):
    """Verify update_transaction_splits handles invalid JSON."""
    register_tools(mcp)

    mock_client = AsyncMock()

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("update_transaction_splits")
            result = await tool.fn(
                transaction_id="txn_123", splits_data="not valid json"
            )

            # Should return error
            assert "error" in result.lower()


@pytest.mark.asyncio
async def test_search_transactions(mcp):
    """Verify search_transactions returns formatted results."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transactions.return_value = {
        "allTransactions": {
            "results": [
                {
                    "id": "txn_1",
                    "date": "2024-01-15",
                    "amount": -25.0,
                    "description": "Coffee Shop",
                    "category": {"name": "Food"},
                    "merchant": {"name": "Starbucks"},
                }
            ]
        }
    }

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("search_transactions")
        result = await tool.fn(query="coffee")

        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["description"] == "Coffee Shop"
        mock_client.get_transactions.assert_called_once()


@pytest.mark.asyncio
async def test_get_transaction_details(mcp):
    """Verify get_transaction_details calls SDK correctly."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transaction_details.return_value = {
        "id": "txn_123",
        "amount": -50.0,
        "notes": "This is a test",
    }

    with patch(
        "monarch_mcp_server.tools.transactions.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transaction_details")
        result = await tool.fn(transaction_id="txn_123")

        data = json.loads(result)
        assert data["id"] == "txn_123"
        mock_client.get_transaction_details.assert_called_once_with("txn_123")
