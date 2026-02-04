"""Tests for tag management tools."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.mark.asyncio
async def test_create_tag_with_default_color(mcp):
    """Verify create_tag uses default gray color when not specified."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.create_transaction_tag.return_value = {
        "id": "tag_123",
        "name": "New Tag",
        "color": "#808080",
    }

    with patch(
        "monarch_mcp_server.tools.tags.get_monarch_client", return_value=mock_client
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("create_tag")
            result = await tool.fn(name="New Tag")

            data = json.loads(result)
            assert data["id"] == "tag_123"
            # Verify default color was passed
            mock_client.create_transaction_tag.assert_called_once_with(
                name="New Tag", color="#808080"
            )


@pytest.mark.asyncio
async def test_create_tag_with_custom_color(mcp):
    """Verify create_tag uses custom color when specified."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.create_transaction_tag.return_value = {
        "id": "tag_456",
        "name": "Important",
        "color": "#FF0000",
    }

    with patch(
        "monarch_mcp_server.tools.tags.get_monarch_client", return_value=mock_client
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("create_tag")
            result = await tool.fn(name="Important", color="#FF0000")

            data = json.loads(result)
            assert data["color"] == "#FF0000"
            mock_client.create_transaction_tag.assert_called_once_with(
                name="Important", color="#FF0000"
            )


@pytest.mark.asyncio
async def test_create_tag_empty_name_error(mcp):
    """Verify create_tag raises error for empty name."""
    register_tools(mcp)

    mock_client = AsyncMock()

    with patch(
        "monarch_mcp_server.tools.tags.get_monarch_client", return_value=mock_client
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("create_tag")
            result = await tool.fn(name="")

            # Should return error message
            assert "error" in result.lower() or "validation" in result.lower()


@pytest.mark.asyncio
async def test_set_transaction_tags_single(mcp):
    """Verify set_transaction_tags handles single tag ID."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.set_transaction_tags.return_value = {"success": True}

    with patch(
        "monarch_mcp_server.tools.tags.get_monarch_client", return_value=mock_client
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("set_transaction_tags")
            result = await tool.fn(transaction_id="txn_123", tag_ids="tag_1")

            data = json.loads(result)
            assert data["success"] is True
            mock_client.set_transaction_tags.assert_called_once_with(
                "txn_123", ["tag_1"]
            )


@pytest.mark.asyncio
async def test_set_transaction_tags_multiple_with_whitespace(mcp):
    """Verify set_transaction_tags handles multiple tags with whitespace."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.set_transaction_tags.return_value = {"success": True}

    with patch(
        "monarch_mcp_server.tools.tags.get_monarch_client", return_value=mock_client
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("set_transaction_tags")
            # Tags with whitespace around them
            result = await tool.fn(
                transaction_id="txn_456", tag_ids="tag_1 , tag_2, tag_3 "
            )

            data = json.loads(result)
            assert data["success"] is True
            # Should strip whitespace from each tag
            mock_client.set_transaction_tags.assert_called_once_with(
                "txn_456", ["tag_1", "tag_2", "tag_3"]
            )
