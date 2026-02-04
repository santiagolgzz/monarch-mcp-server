"""
Metadata tools for Monarch Money.

Tools for retrieving subscription details and institution information.
"""

import logging

from fastmcp import FastMCP

from monarch_mcp_server.client import get_monarch_client

from ._common import tool_handler

logger = logging.getLogger(__name__)


def register_metadata_tools(mcp: FastMCP) -> None:
    """Register metadata tools with the FastMCP instance."""

    @mcp.tool()
    @tool_handler("get_subscription_details")
    async def get_subscription_details() -> dict:
        """Get Monarch Money subscription details (account status, paid/trial)."""
        client = await get_monarch_client()
        return await client.get_subscription_details()

    @mcp.tool()
    @tool_handler("get_institutions")
    async def get_institutions() -> dict:
        """Get all linked financial institutions."""
        client = await get_monarch_client()
        return await client.get_institutions()
