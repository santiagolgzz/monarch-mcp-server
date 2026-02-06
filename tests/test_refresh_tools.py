"""Tests for account refresh tools."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.mark.asyncio
async def test_is_accounts_refresh_complete_true(mcp):
    """Verify is_accounts_refresh_complete returns true when complete."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.is_accounts_refresh_complete.return_value = True

    with patch(
        "monarch_mcp_server.tools.refresh.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("is_accounts_refresh_complete")
        data = await tool.fn()
        assert data["refresh_complete"] is True
        mock_client.is_accounts_refresh_complete.assert_called_once()


@pytest.mark.asyncio
async def test_is_accounts_refresh_complete_false(mcp):
    """Verify is_accounts_refresh_complete returns false when not complete."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.is_accounts_refresh_complete.return_value = False

    with patch(
        "monarch_mcp_server.tools.refresh.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("is_accounts_refresh_complete")
        data = await tool.fn()
        assert data["refresh_complete"] is False


@pytest.mark.asyncio
async def test_refresh_accounts_success(mcp):
    """Verify refresh_accounts refreshes all accounts."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_accounts.return_value = {
        "accounts": [
            {"id": "acc_1", "displayName": "Checking"},
            {"id": "acc_2", "displayName": "Savings"},
        ]
    }
    mock_client.request_accounts_refresh.return_value = True

    with patch(
        "monarch_mcp_server.tools.refresh.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("refresh_accounts")
        data = await tool.fn()
        assert data["refreshed"] is True
        mock_client.request_accounts_refresh.assert_called_once_with(["acc_1", "acc_2"])


@pytest.mark.asyncio
async def test_refresh_accounts_no_accounts(mcp):
    """Verify refresh_accounts handles empty accounts list."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_accounts.return_value = {"accounts": []}

    with patch(
        "monarch_mcp_server.tools.refresh.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("refresh_accounts")
        data = await tool.fn()
        assert data["refreshed"] is False
        assert "No accounts found" in data["message"]
        # Should not call request_accounts_refresh when no accounts
        mock_client.request_accounts_refresh.assert_not_called()


@pytest.mark.asyncio
async def test_request_accounts_refresh_and_wait_success(mcp):
    """Verify request_accounts_refresh_and_wait waits for completion."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.request_accounts_refresh_and_wait.return_value = True

    with patch(
        "monarch_mcp_server.tools.refresh.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("request_accounts_refresh_and_wait")
        data = await tool.fn()
        assert data["success"] is True
        mock_client.request_accounts_refresh_and_wait.assert_called_once()


@pytest.mark.asyncio
async def test_request_accounts_refresh_and_wait_failure(mcp):
    """Verify request_accounts_refresh_and_wait handles failure."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.request_accounts_refresh_and_wait.return_value = False

    with patch(
        "monarch_mcp_server.tools.refresh.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("request_accounts_refresh_and_wait")
        data = await tool.fn()
        assert data["success"] is False


@pytest.mark.asyncio
async def test_refresh_accounts_missing_accounts_key(mcp):
    """Verify refresh_accounts handles missing accounts key."""
    register_tools(mcp)

    mock_client = AsyncMock()
    # Return dict without accounts key
    mock_client.get_accounts.return_value = {}

    with patch(
        "monarch_mcp_server.tools.refresh.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp._tool_manager.get_tool("refresh_accounts")
        data = await tool.fn()
        assert data["refreshed"] is False
        assert "No accounts found" in data["message"]
