"""
Tag management tools for Monarch Money.

Tools for creating and managing transaction tags.
"""

import logging

from fastmcp import FastMCP

from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.safety import require_safety_check
from monarch_mcp_server.utils import validate_non_empty_string

from ._common import tool_handler

logger = logging.getLogger(__name__)


def register_tag_tools(mcp: FastMCP) -> None:
    """Register tag management tools with the FastMCP instance."""

    @mcp.tool()
    @require_safety_check("create_tag")
    @tool_handler("create_tag")
    async def create_tag(name: str, color: str | None = None) -> dict:
        """Create a new transaction tag."""
        validate_non_empty_string(name, "name")
        client = await get_monarch_client()
        tag_color = color or "#808080"
        return await client.create_transaction_tag(name=name, color=tag_color)

    @mcp.tool()
    @require_safety_check("set_transaction_tags")
    @tool_handler("set_transaction_tags")
    async def set_transaction_tags(transaction_id: str, tag_ids: str) -> dict:
        """Assign tags to a transaction."""
        client = await get_monarch_client()
        ids_list = [id.strip() for id in tag_ids.split(",")]
        return await client.set_transaction_tags(transaction_id, ids_list)
