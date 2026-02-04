import json
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
        result = await tool.fn()

        data = json.loads(result)
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
        result = await tool.fn()

        data = json.loads(result)
        assert data == []
