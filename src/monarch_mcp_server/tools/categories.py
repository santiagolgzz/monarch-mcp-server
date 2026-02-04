"""
Category management tools for Monarch Money.

Tools for viewing and managing transaction categories and groups.
"""

import logging

from fastmcp import FastMCP

from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.safety import require_safety_check
from monarch_mcp_server.utils import validate_non_empty_string

from ._common import tool_handler

logger = logging.getLogger(__name__)


def register_category_tools(mcp: FastMCP) -> None:
    """Register category management tools with the FastMCP instance."""

    @mcp.tool()
    @tool_handler("get_transaction_categories")
    async def get_transaction_categories() -> list[dict]:
        """Get all transaction categories from Monarch Money with their IDs."""
        client = await get_monarch_client()
        categories = await client.get_transaction_categories()
        category_list = []
        for cat in categories.get("categories", []):
            category_info = {
                "id": cat.get("id"),
                "name": cat.get("name"),
                "icon": cat.get("icon"),
                "group": cat.get("group", {}).get("name") if cat.get("group") else None,
            }
            category_list.append(category_info)
        return category_list

    @mcp.tool()
    @tool_handler("get_transaction_category_groups")
    async def get_transaction_category_groups() -> dict:
        """Get all category groups."""
        client = await get_monarch_client()
        return await client.get_transaction_category_groups()

    @mcp.tool()
    @tool_handler("get_transaction_tags")
    async def get_transaction_tags() -> list[dict]:
        """Get all transaction tags."""
        client = await get_monarch_client()
        tags = await client.get_transaction_tags()
        tag_list = []
        for tag in tags.get("transactionTags", []):
            tag_info = {
                "id": tag.get("id"),
                "name": tag.get("name"),
                "color": tag.get("color"),
            }
            tag_list.append(tag_info)
        return tag_list

    @mcp.tool()
    @require_safety_check("create_transaction_category")
    @tool_handler("create_transaction_category")
    async def create_transaction_category(name: str, group_id: str) -> dict:
        """Create a new transaction category."""
        validate_non_empty_string(group_id, "group_id")
        client = await get_monarch_client()
        return await client.create_transaction_category(
            group_id=group_id, transaction_category_name=name
        )

    @mcp.tool()
    @require_safety_check("delete_transaction_category")
    @tool_handler("delete_transaction_category")
    async def delete_transaction_category(category_id: str) -> dict:
        """Delete a transaction category."""
        client = await get_monarch_client()
        result = await client.delete_transaction_category(category_id)
        return {"deleted": result, "category_id": category_id}

    @mcp.tool()
    @require_safety_check("delete_transaction_categories")
    @tool_handler("delete_transaction_categories")
    async def delete_transaction_categories(category_ids: str) -> dict:
        """Delete multiple transaction categories."""
        client = await get_monarch_client()
        ids_list = [id.strip() for id in category_ids.split(",")]
        results = await client.delete_transaction_categories(ids_list)
        # Map results to category IDs for clearer output
        return {
            "results": [
                {"category_id": cid, "deleted": isinstance(r, bool) and r, "error": str(r) if isinstance(r, BaseException) else None}
                for cid, r in zip(ids_list, results)
            ]
        }
