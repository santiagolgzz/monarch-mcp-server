"""Tests for category management tools."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.mark.asyncio
async def test_get_categories_with_group(mcp):
    """Verify get_transaction_categories returns categories with groups."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transaction_categories.return_value = {
        "categories": [
            {
                "id": "cat_1",
                "name": "Groceries",
                "icon": "cart",
                "group": {"name": "Food & Dining"},
            },
            {
                "id": "cat_2",
                "name": "Gas",
                "icon": "fuel",
                "group": {"name": "Auto & Transport"},
            },
        ]
    }

    with patch(
        "monarch_mcp_server.tools.categories.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transaction_categories")
        result = await tool.fn()

        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["name"] == "Groceries"
        assert data[0]["group"] == "Food & Dining"
        assert data[1]["group"] == "Auto & Transport"


@pytest.mark.asyncio
async def test_get_categories_null_group(mcp):
    """Verify get_transaction_categories handles null group."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transaction_categories.return_value = {
        "categories": [
            {
                "id": "cat_1",
                "name": "Uncategorized",
                "icon": None,
                "group": None,  # No group
            }
        ]
    }

    with patch(
        "monarch_mcp_server.tools.categories.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transaction_categories")
        result = await tool.fn()

        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["group"] is None


@pytest.mark.asyncio
async def test_get_tags_missing_color(mcp):
    """Verify get_transaction_tags handles tags without color."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transaction_tags.return_value = {
        "transactionTags": [
            {
                "id": "tag_1",
                "name": "Important",
                # No color field
            }
        ]
    }

    with patch(
        "monarch_mcp_server.tools.categories.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transaction_tags")
        result = await tool.fn()

        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["name"] == "Important"
        assert data[0]["color"] is None


@pytest.mark.asyncio
async def test_get_category_groups(mcp):
    """Verify get_transaction_category_groups returns groups."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_transaction_category_groups.return_value = {
        "groups": [
            {"id": "grp_1", "name": "Food & Dining"},
            {"id": "grp_2", "name": "Auto & Transport"},
        ]
    }

    with patch(
        "monarch_mcp_server.tools.categories.get_monarch_client",
        return_value=mock_client,
    ):
        tool = await mcp._tool_manager.get_tool("get_transaction_category_groups")
        result = await tool.fn()

        data = json.loads(result)
        assert "groups" in data
        mock_client.get_transaction_category_groups.assert_called_once()


@pytest.mark.asyncio
async def test_create_category_validation(mcp):
    """Verify create_transaction_category validates group_id."""
    register_tools(mcp)

    mock_client = AsyncMock()

    with patch(
        "monarch_mcp_server.tools.categories.get_monarch_client",
        return_value=mock_client,
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("create_transaction_category")
            result = await tool.fn(name="New Category", group_id="")

            # Should return error for empty group_id
            assert "error" in result.lower() or "validation" in result.lower()


@pytest.mark.asyncio
async def test_create_category_success(mcp):
    """Verify create_transaction_category creates category."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.create_transaction_category.return_value = {
        "id": "new_cat_123",
        "name": "Coffee",
    }

    with patch(
        "monarch_mcp_server.tools.categories.get_monarch_client",
        return_value=mock_client,
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("create_transaction_category")
            result = await tool.fn(name="Coffee", group_id="grp_food")

            data = json.loads(result)
            assert data["id"] == "new_cat_123"
            mock_client.create_transaction_category.assert_called_once_with(
                group_id="grp_food", transaction_category_name="Coffee"
            )


@pytest.mark.asyncio
async def test_delete_category_false_result(mcp):
    """Verify delete_transaction_category handles False SDK result."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.delete_transaction_category.return_value = False

    with patch(
        "monarch_mcp_server.tools.categories.get_monarch_client",
        return_value=mock_client,
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("delete_transaction_category")
            result = await tool.fn(category_id="cat_123")

            data = json.loads(result)
            assert data["deleted"] is False
            assert data["category_id"] == "cat_123"


@pytest.mark.asyncio
async def test_delete_categories_mixed_results(mcp):
    """Verify delete_transaction_categories handles mixed success/failure."""
    register_tools(mcp)

    mock_client = AsyncMock()
    # SDK returns list of results - one success, one failure
    mock_client.delete_transaction_categories.return_value = [
        True,
        Exception("Category in use"),
    ]

    with patch(
        "monarch_mcp_server.tools.categories.get_monarch_client",
        return_value=mock_client,
    ):
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            mock_guard.return_value.check_operation.return_value = (True, None)

            tool = await mcp._tool_manager.get_tool("delete_transaction_categories")
            result = await tool.fn(category_ids="cat_1,cat_2")

            data = json.loads(result)
            assert "results" in data
            assert len(data["results"]) == 2
            assert data["results"][0]["deleted"] is True
            assert data["results"][0]["category_id"] == "cat_1"
            assert data["results"][1]["deleted"] is False
            assert data["results"][1]["error"] is not None
