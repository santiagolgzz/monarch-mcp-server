"""
Account management tools for Monarch Money.

Tools for viewing and managing financial accounts.
"""

import logging

from fastmcp import FastMCP

from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.exceptions import ValidationError
from monarch_mcp_server.safety import require_safety_check
from monarch_mcp_server.utils import validate_non_empty_string

from ._common import tool_handler

logger = logging.getLogger(__name__)


def register_account_tools(mcp: FastMCP) -> None:
    """Register account management tools with the FastMCP instance."""

    @mcp.tool()
    @tool_handler("get_accounts")
    async def get_accounts() -> list[dict]:
        """Get all financial accounts from Monarch Money."""
        client = await get_monarch_client()
        accounts = await client.get_accounts()
        account_list = []
        for account in accounts.get("accounts", []):
            account_info = {
                "id": account.get("id"),
                "name": account.get("displayName") or account.get("name"),
                "type": (account.get("type") or {}).get("name"),
                "balance": account.get("currentBalance"),
                "institution": (account.get("institution") or {}).get("name"),
                "is_active": account.get("isActive")
                if "isActive" in account
                else not account.get("deactivatedAt"),
            }
            account_list.append(account_info)
        return account_list

    @mcp.tool()
    @tool_handler("get_account_holdings")
    async def get_account_holdings(account_id: str) -> dict:
        """Get investment holdings for a specific account."""
        try:
            acc_id = int(account_id)
        except ValueError:
            raise ValidationError(f"Invalid account_id: {account_id}. Must be numeric.")

        client = await get_monarch_client()
        return await client.get_account_holdings(acc_id)

    @mcp.tool()
    @tool_handler("get_account_history")
    async def get_account_history(
        account_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Get daily account balance history for a specific account."""
        try:
            acc_id = int(account_id)
        except ValueError:
            raise ValidationError(f"Invalid account_id: {account_id}. Must be numeric.")

        client = await get_monarch_client()
        history_data = await client.get_account_history(account_id=acc_id)

        # Handle both dict and list return types from SDK
        if isinstance(history_data, dict):
            entries = history_data.get("history", [])
        elif isinstance(history_data, list):
            entries = history_data
        else:
            entries = []

        if start_date or end_date:
            filtered_entries = []
            for entry in entries:
                entry_date = entry.get("date")
                if not entry_date:
                    filtered_entries.append(entry)
                    continue
                if start_date and entry_date < start_date:
                    continue
                if end_date and entry_date > end_date:
                    continue
                filtered_entries.append(entry)
            return {"history": filtered_entries}

        return {"history": entries}

    @mcp.tool()
    @tool_handler("get_account_type_options")
    async def get_account_type_options() -> dict:
        """Get all available account types and subtypes."""
        client = await get_monarch_client()
        return await client.get_account_type_options()

    @mcp.tool()
    @require_safety_check("create_manual_account")
    @tool_handler("create_manual_account")
    async def create_manual_account(
        account_name: str,
        account_type: str,
        current_balance: float,
        account_subtype: str | None = None,
    ) -> dict:
        """Create a manual account."""
        validate_non_empty_string(account_name, "account_name")
        validate_non_empty_string(account_type, "account_type")

        client = await get_monarch_client()
        return await client.create_manual_account(
            account_type=account_type,
            account_sub_type=account_subtype or account_type,
            is_in_net_worth=True,
            account_name=account_name,
            account_balance=current_balance,
        )

    @mcp.tool()
    @require_safety_check("update_account")
    @tool_handler("update_account")
    async def update_account(
        account_id: str,
        name: str | None = None,
        balance: float | None = None,
        account_type: str | None = None,
    ) -> dict:
        """Update account settings or balance."""
        client = await get_monarch_client()
        return await client.update_account(
            account_id=account_id,
            account_name=name,
            account_balance=balance,
            account_type=account_type,
        )

    @mcp.tool()
    @require_safety_check("delete_account")
    @tool_handler("delete_account")
    async def delete_account(account_id: str) -> dict:
        """Delete an account from Monarch Money."""
        client = await get_monarch_client()
        result = await client.delete_account(account_id)
        # SDK returns bool, wrap for consistency
        if isinstance(result, bool):
            return {"deleted": result, "account_id": account_id}
        return result

    @mcp.tool()
    @require_safety_check("upload_account_balance_history")
    @tool_handler("upload_account_balance_history")
    async def upload_account_balance_history(account_id: str, csv_data: str) -> dict:
        """Upload account balance history from CSV data."""
        client = await get_monarch_client()
        await client.upload_account_balance_history(account_id, csv_data)
        # SDK returns None on success
        return {"uploaded": True, "account_id": account_id}
