"""
Account refresh tools for Monarch Money.

Tools for refreshing account data from financial institutions.
"""

import logging

from fastmcp import FastMCP

from monarch_mcp_server.client import get_monarch_client

from ._common import tool_handler

logger = logging.getLogger(__name__)


def register_refresh_tools(mcp: FastMCP) -> None:
    """Register account refresh tools with the FastMCP instance."""

    @mcp.tool()
    @tool_handler("is_accounts_refresh_complete")
    async def is_accounts_refresh_complete() -> dict:
        """Check if account refresh/synchronization is complete."""
        client = await get_monarch_client()
        result = await client.is_accounts_refresh_complete()
        return {"refresh_complete": result}

    @mcp.tool()
    @tool_handler("refresh_accounts")
    async def refresh_accounts() -> dict:
        """Request account data refresh from financial institutions."""
        client = await get_monarch_client()
        # Get all accounts to refresh
        accounts = await client.get_accounts()
        account_ids = [acc["id"] for acc in accounts.get("accounts", [])]
        if not account_ids:
            return {"refreshed": False, "message": "No accounts found to refresh"}
        result = await client.request_accounts_refresh(account_ids)
        return {"refreshed": result}

    @mcp.tool()
    @tool_handler("request_accounts_refresh_and_wait")
    async def request_accounts_refresh_and_wait() -> dict:
        """Request account refresh and wait for completion (blocking operation)."""
        client = await get_monarch_client()
        result = await client.request_accounts_refresh_and_wait()
        return {"success": result}
