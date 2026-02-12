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
    @tool_handler("check_auth_status")
    async def check_auth_status() -> str:
        """Check if already authenticated with Monarch Money.

        Verifies the connection by making a lightweight API call to Monarch's servers.
        Works for both local (keyring) and remote (env var) authentication modes.
        """
        try:
            client = await get_monarch_client()
            subscription = await client.get_subscription_details()

            is_paid = subscription.get("hasPremiumEntitlement", False)
            plan_type = "Premium" if is_paid else "Free/Trial"

            return f"Authenticated and connected to Monarch Money. Plan: {plan_type}"

        except Exception as e:
            error_msg = str(e)
            if "Authentication required" in error_msg:
                return (
                    "Not authenticated. "
                    "For local use: Run `python login_setup.py`. "
                    "For remote use: Set MONARCH_EMAIL and MONARCH_PASSWORD env vars."
                )
            return f"Connection failed: {error_msg}"

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
