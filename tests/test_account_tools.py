from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.mark.asyncio
async def test_get_accounts_async(mcp):
    """Verify get_accounts is registered and works asynchronously."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_accounts.return_value = {
        "accounts": [
            {
                "id": "1",
                "displayName": "Test",
                "type": {"name": "checking"},
                "currentBalance": 100,
                "institution": {"name": "Bank"},
            }
        ]
    }

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_accounts")
        data = await tool.fn()
        assert len(data) == 1
        assert data[0]["name"] == "Test"


@pytest.mark.asyncio
async def test_get_account_history_consistency(mcp):
    """Verify get_account_history return format is consistent."""
    register_tools(mcp)

    mock_client = AsyncMock()
    # Mock return from SDK
    mock_client.get_account_history.return_value = {
        "history": [{"date": "2024-01-01", "balance": 100}]
    }

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_account_history")
        # Test without filtering
        data = await tool.fn(account_id="1")
        assert "history" in data
        assert len(data["history"]) == 1


@pytest.mark.asyncio
async def test_account_id_casting_safety(mcp):
    """Verify that passing an invalid account_id doesn't crash the server."""
    register_tools(mcp)

    mock_client = AsyncMock()
    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_account_holdings")
        # Test with invalid ID
        with pytest.raises(RuntimeError, match="Invalid account_id"):
            await tool.fn(account_id="invalid")


@pytest.mark.asyncio
async def test_get_account_holdings_valid_id(mcp):
    """Verify get_account_holdings works with valid numeric ID."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_account_holdings.return_value = {
        "holdings": [
            {"symbol": "AAPL", "shares": 10, "value": 1750.0},
            {"symbol": "GOOG", "shares": 5, "value": 7000.0},
        ]
    }

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_account_holdings")
        data = await tool.fn(account_id="12345")
        assert "holdings" in data
        assert len(data["holdings"]) == 2
        mock_client.get_account_holdings.assert_called_once_with(12345)


@pytest.mark.asyncio
async def test_get_account_history_date_filtering(mcp):
    """Verify get_account_history filters by date range."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_account_history.return_value = {
        "history": [
            {"date": "2024-01-01", "balance": 100},
            {"date": "2024-01-15", "balance": 150},
            {"date": "2024-02-01", "balance": 200},
        ]
    }

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_account_history")
        data = await tool.fn(
            account_id="1", start_date="2024-01-10", end_date="2024-01-20"
        )
        assert len(data["history"]) == 1
        assert data["history"][0]["date"] == "2024-01-15"


@pytest.mark.asyncio
async def test_get_account_history_list_format(mcp):
    """Verify get_account_history handles SDK returning a list."""
    register_tools(mcp)

    mock_client = AsyncMock()
    # SDK might return list instead of dict
    mock_client.get_account_history.return_value = [
        {"date": "2024-01-01", "balance": 100},
        {"date": "2024-01-02", "balance": 110},
    ]

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_account_history")
        data = await tool.fn(account_id="1")
        assert "history" in data
        assert len(data["history"]) == 2


@pytest.mark.asyncio
async def test_get_account_type_options(mcp):
    """Verify get_account_type_options returns account types."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_account_type_options.return_value = {
        "types": [
            {"name": "checking", "subtypes": ["regular", "interest"]},
            {"name": "savings", "subtypes": ["regular", "high-yield"]},
        ]
    }

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_account_type_options")
        data = await tool.fn()
        assert "types" in data
        mock_client.get_account_type_options.assert_called_once()


@pytest.mark.asyncio
async def test_create_manual_account_success(mcp):
    """Verify create_manual_account creates account with correct params."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.create_manual_account.return_value = {
        "id": "new_acc_123",
        "name": "My New Account",
    }

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("create_manual_account")
            data = await tool.fn(
                account_name="My New Account",
                account_type="checking",
                current_balance=1000.0,
            )
            assert data["id"] == "new_acc_123"
            mock_client.create_manual_account.assert_called_once()


@pytest.mark.asyncio
async def test_create_manual_account_with_subtype(mcp):
    """Verify create_manual_account passes subtype correctly."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.create_manual_account.return_value = {"id": "acc_456"}

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("create_manual_account")
            await tool.fn(
                account_name="Investment",
                account_type="investment",
                current_balance=5000.0,
                account_subtype="brokerage",
            )

            call_kwargs = mock_client.create_manual_account.call_args.kwargs
            assert call_kwargs["account_sub_type"] == "brokerage"


@pytest.mark.asyncio
async def test_update_account_success(mcp):
    """Verify update_account calls SDK correctly."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.update_account.return_value = {
        "id": "acc_123",
        "name": "Updated Name",
    }

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("update_account")
            data = await tool.fn(account_id="acc_123", name="Updated Name")
            assert data["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_account_bool_result(mcp):
    """Verify delete_account wraps bool result in dict."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.delete_account.return_value = True  # SDK returns bool

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("delete_account")
            data = await tool.fn(account_id="acc_to_delete")
            assert data["deleted"] is True
            assert data["account_id"] == "acc_to_delete"


@pytest.mark.asyncio
async def test_upload_account_balance_history(mcp):
    """Verify upload_account_balance_history calls SDK."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.upload_account_balance_history.return_value = None  # SDK returns None

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("upload_account_balance_history")
            csv_data = "date,balance\n2024-01-01,1000\n2024-01-02,1050"
            data = await tool.fn(account_id="acc_123", csv_data=csv_data)
            assert data["uploaded"] is True
            assert data["account_id"] == "acc_123"


@pytest.mark.asyncio
async def test_get_accounts_name_fallback(mcp):
    """Verify get_accounts falls back to 'name' when displayName is missing."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_accounts.return_value = {
        "accounts": [
            {
                "id": "1",
                "name": "Fallback Name",
                # No displayName
                "type": {"name": "savings"},
                "currentBalance": 500,
                "institution": {"name": "Credit Union"},
            }
        ]
    }

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_accounts")
        data = await tool.fn()
        assert data[0]["name"] == "Fallback Name"


@pytest.mark.asyncio
async def test_get_accounts_missing_type(mcp):
    """Verify get_accounts handles missing type gracefully."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_accounts.return_value = {
        "accounts": [
            {
                "id": "1",
                "displayName": "Test Account",
                "type": None,  # No type
                "currentBalance": 100,
                "institution": None,  # No institution
            }
        ]
    }

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_accounts")
        data = await tool.fn()
        assert data[0]["type"] is None
        assert data[0]["institution"] is None


@pytest.mark.asyncio
async def test_get_accounts_is_active_field(mcp):
    """Verify get_accounts computes is_active correctly."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_accounts.return_value = {
        "accounts": [
            {
                "id": "1",
                "displayName": "Active Account",
                "type": {"name": "checking"},
                "currentBalance": 100,
                "institution": {"name": "Bank"},
                "isActive": True,
            },
            {
                "id": "2",
                "displayName": "Deactivated Account",
                "type": {"name": "checking"},
                "currentBalance": 0,
                "institution": {"name": "Bank"},
                "deactivatedAt": "2024-01-01T00:00:00Z",
            },
        ]
    }

    with patch(
        "monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("get_accounts")
        data = await tool.fn()
        assert data[0]["is_active"] is True
        assert data[1]["is_active"] is False
