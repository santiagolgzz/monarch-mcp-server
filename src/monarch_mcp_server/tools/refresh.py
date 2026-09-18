"""
Account refresh tools for Monarch Money.

Tools for refreshing account data from financial institutions.

Every tool here accepts an optional ``account_ids``. Omitting it targets all
accounts; passing a list targets exactly those accounts. A single account is
just a one-element list, so one account, a subset, and everything are all
reachable without separate tools.
"""

import logging

from fastmcp import FastMCP

from monarch_mcp_server.client import get_monarch_client

from ._common import tool_handler

logger = logging.getLogger(__name__)


async def _resolve_account_ids(client, account_ids: list[str] | None) -> list[str]:
    """Return the account IDs to act on.

    ``None`` means every account, which requires a lookup. An explicit list is
    used as given. An empty list is treated as "none specified" rather than
    "no accounts", since refreshing nothing is never the intent.
    """
    if account_ids:
        return account_ids
    accounts = await client.get_accounts()
    return [acc["id"] for acc in accounts.get("accounts", [])]


def register_refresh_tools(mcp: FastMCP) -> None:
    """Register account refresh tools with the FastMCP instance."""

    @mcp.tool()
    @tool_handler("is_accounts_refresh_complete")
    async def is_accounts_refresh_complete(
        account_ids: list[str] | None = None,
    ) -> dict:
        """Check whether an account refresh has finished.

        Args:
            account_ids: Only check these accounts. Omit to check all accounts.
        """
        client = await get_monarch_client()
        result = await client.is_accounts_refresh_complete(account_ids=account_ids)
        return {
            "refresh_complete": result,
            "account_ids": account_ids,
            "scope": "all" if not account_ids else "selected",
        }

    @mcp.tool()
    @tool_handler("refresh_accounts")
    async def refresh_accounts(account_ids: list[str] | None = None) -> dict:
        """Request an account data refresh from financial institutions.

        Args:
            account_ids: Refresh only these accounts. Pass a single-element
                list for one account, several IDs for a subset, or omit it
                entirely to refresh every account.
        """
        client = await get_monarch_client()
        resolved = await _resolve_account_ids(client, account_ids)
        if not resolved:
            return {"refreshed": False, "message": "No accounts found to refresh"}

        result = await client.request_accounts_refresh(resolved)
        return {
            "refreshed": result,
            "account_ids": resolved,
            "account_count": len(resolved),
            "scope": "all" if not account_ids else "selected",
        }

    @mcp.tool()
    @tool_handler("request_accounts_refresh_and_wait")
    async def request_accounts_refresh_and_wait(
        account_ids: list[str] | None = None,
        timeout: int = 300,
        delay: int = 10,
    ) -> dict:
        """Request an account refresh and wait for it to finish (blocking).

        Args:
            account_ids: Refresh only these accounts. Pass a single-element
                list for one account, several IDs for a subset, or omit it
                entirely to refresh every account.
            timeout: Seconds to wait before giving up. Default 300.
            delay: Seconds between completion checks. Default 10.
        """
        client = await get_monarch_client()
        result = await client.request_accounts_refresh_and_wait(
            account_ids=account_ids,
            timeout=timeout,
            delay=delay,
        )
        return {
            "success": result,
            "account_ids": account_ids,
            "scope": "all" if not account_ids else "selected",
            "timeout": timeout,
            "delay": delay,
        }
