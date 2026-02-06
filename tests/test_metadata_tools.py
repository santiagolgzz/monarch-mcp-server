from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.mark.asyncio
async def test_get_transaction_categories_async(mcp):
    """Verify get_transaction_categories is registered and works asynchronously."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transaction_categories.return_value = {"categories": []}

    with patch(
        "monarch_mcp_server.tools.categories.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transaction_categories")
        data = await tool.fn()
        assert data == []


@pytest.mark.asyncio
async def test_get_transaction_tags_async(mcp):
    """Verify get_transaction_tags is registered and works asynchronously."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transaction_tags.return_value = {"transactionTags": []}

    with patch(
        "monarch_mcp_server.tools.categories.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transaction_tags")
        data = await tool.fn()
        assert data == []


@pytest.mark.asyncio
async def test_get_subscription_details_success(mcp):
    """Verify get_subscription_details returns subscription info."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_subscription_details.return_value = {
        "subscription": {
            "status": "active",
            "plan": "premium",
            "expires": "2025-01-01",
        }
    }

    with patch(
        "monarch_mcp_server.tools.metadata.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_subscription_details")
        data = await tool.fn()
        assert "subscription" in data
        mock_client.get_subscription_details.assert_called_once()


@pytest.mark.asyncio
async def test_get_subscription_details_error(mcp):
    """Verify get_subscription_details handles errors gracefully."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_subscription_details.side_effect = Exception("API error")

    with patch(
        "monarch_mcp_server.tools.metadata.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_subscription_details")
        with pytest.raises(RuntimeError, match="API error"):
            await tool.fn()


@pytest.mark.asyncio
async def test_get_institutions_success(mcp):
    """Verify get_institutions returns linked institutions."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_institutions.return_value = {
        "institutions": [
            {"id": "inst_1", "name": "Chase Bank", "status": "connected"},
            {"id": "inst_2", "name": "Wells Fargo", "status": "needs_attention"},
        ]
    }

    with patch(
        "monarch_mcp_server.tools.metadata.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_institutions")
        data = await tool.fn()
        assert "institutions" in data
        assert len(data["institutions"]) == 2
        mock_client.get_institutions.assert_called_once()


@pytest.mark.asyncio
async def test_get_institutions_error(mcp):
    """Verify get_institutions handles errors gracefully."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_institutions.side_effect = Exception("Network error")

    with patch(
        "monarch_mcp_server.tools.metadata.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_institutions")
        with pytest.raises(RuntimeError, match="Network error"):
            await tool.fn()


@pytest.mark.asyncio
async def test_get_subscription_with_trial_data(mcp):
    """Verify get_subscription_details handles trial subscription."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_subscription_details.return_value = {
        "subscription": {
            "status": "trial",
            "trialEnds": "2024-02-01",
        }
    }

    with patch(
        "monarch_mcp_server.tools.metadata.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_subscription_details")
        data = await tool.fn()
        assert data["subscription"]["status"] == "trial"


@pytest.mark.asyncio
async def test_get_institutions_empty(mcp):
    """Verify get_institutions handles empty institutions list."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_institutions.return_value = {"institutions": []}

    with patch(
        "monarch_mcp_server.tools.metadata.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_institutions")
        data = await tool.fn()
        assert data["institutions"] == []
