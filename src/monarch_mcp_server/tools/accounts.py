"""
Account management tools for Monarch Money.

Tools for viewing and managing financial accounts.
"""

import csv
import io
import logging
from datetime import datetime

from fastmcp import FastMCP
from monarchmoney.monarchmoney import BalanceHistoryRow

from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.exceptions import ValidationError
from monarch_mcp_server.safety import require_safety_check
from monarch_mcp_server.utils import validate_date_format, validate_non_empty_string

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
    @tool_handler("get_recent_account_balances")
    async def get_recent_account_balances(start_date: str | None = None) -> dict:
        """Get daily balances for all accounts (defaults to last 31 days).

        Args:
            start_date: Start date in YYYY-MM-DD format. Defaults to 31 days ago.
        """
        validated_start = validate_date_format(start_date, "start_date")
        client = await get_monarch_client()
        return await client.get_recent_account_balances(start_date=validated_start)

    @mcp.tool()
    @tool_handler("get_account_snapshots_by_type")
    async def get_account_snapshots_by_type(
        start_date: str,
        timeframe: str = "month",
    ) -> dict:
        """Get net value snapshots grouped by account type.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            timeframe: Granularity — "month" or "year".
        """
        validated_start = validate_date_format(start_date, "start_date")
        assert validated_start is not None
        if timeframe not in ("month", "year"):
            raise ValidationError(
                f"timeframe must be 'month' or 'year', got '{timeframe}'"
            )
        client = await get_monarch_client()
        return await client.get_account_snapshots_by_type(
            start_date=validated_start, timeframe=timeframe
        )

    @mcp.tool()
    @tool_handler("get_aggregate_snapshots")
    async def get_aggregate_snapshots(
        start_date: str | None = None,
        end_date: str | None = None,
        account_type: str | None = None,
    ) -> dict:
        """Get daily aggregate net value across all accounts.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            account_type: Optional account type filter.
        """
        from datetime import date as date_type

        validated_start = validate_date_format(start_date, "start_date")
        validated_end = validate_date_format(end_date, "end_date")

        # SDK expects datetime.date objects, not strings
        start_d = date_type.fromisoformat(validated_start) if validated_start else None
        end_d = date_type.fromisoformat(validated_end) if validated_end else None

        client = await get_monarch_client()
        return await client.get_aggregate_snapshots(
            start_date=start_d, end_date=end_d, account_type=account_type
        )

    @mcp.tool()
    @tool_handler("get_credit_history")
    async def get_credit_history() -> dict:
        """Get credit score history from Monarch Money.

        Returns the credit score data Monarch tracks over time. Requires
        credit monitoring to be enabled on the account; otherwise the
        response will be empty.
        """
        client = await get_monarch_client()
        return await client.get_credit_history()

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
        account_sub_type: str | None = None,
        include_in_net_worth: bool | None = None,
        hide_from_summary_list: bool | None = None,
        hide_transactions_from_reports: bool | None = None,
    ) -> dict:
        """Update account settings or balance.

        Every field is optional; omitting one leaves it unchanged. The SDK
        skips None values, so they are passed through directly rather than
        being filtered out here.

        Args:
            account_id: The account to update.
            name: New display name.
            balance: New displayed balance.
            account_type: New account type.
            account_sub_type: New account subtype.
            include_in_net_worth: Whether this account counts toward net worth.
            hide_from_summary_list: Hide the account from the summary list.
            hide_transactions_from_reports: Exclude this account's transactions
                from reports.
        """
        client = await get_monarch_client()
        return await client.update_account(
            account_id=account_id,
            account_name=name,
            account_balance=balance,
            account_type=account_type,
            account_sub_type=account_sub_type,
            include_in_net_worth=include_in_net_worth,
            hide_from_summary_list=hide_from_summary_list,
            hide_transactions_from_reports=hide_transactions_from_reports,
        )

    @mcp.tool()
    @require_safety_check("delete_account")
    @tool_handler("delete_account")
    async def delete_account(
        account_id: str,
        confirmation_token: str | None = None,
    ) -> dict:
        """Delete an account from Monarch Money.

        Deleting an account also removes its transaction history, which this
        server cannot restore.

        Args:
            account_id: The account to delete.
            confirmation_token: Leave unset on the first call. The server
                replies with a token and a description of what will be
                destroyed; repeat the call with that token to carry it out.
                The token works once, only for these exact arguments, and
                expires.
        """
        client = await get_monarch_client()
        result = await client.delete_account(account_id)
        # SDK returns bool, wrap for consistency
        if isinstance(result, bool):
            return {"deleted": result, "account_id": account_id}
        return result

    @mcp.tool()
    @require_safety_check("upload_account_balance_history")
    @tool_handler("upload_account_balance_history")
    async def upload_account_balance_history(
        account_id: str,
        csv_data: str,
        timeout: int = 300,
        delay: int = 10,
        confirmation_token: str | None = None,
    ) -> dict:
        """Upload account balance history from CSV data.

        csv_data should be CSV text with columns: date, amount
        (and optional account_name). Dates should be in YYYY-MM-DD format.

        Args:
            account_id: The account to upload history for.
            csv_data: CSV text as described above.
            timeout: Seconds to wait for the upload to be processed. Default 300.
            delay: Seconds between status checks while waiting. Default 10.
            confirmation_token: Leave unset on the first call. The server
                replies with a token and a description of what will be
                overwritten; repeat the call with that token to carry it out.
                The token works once, only for these exact arguments, and
                expires. This upload overwrites existing balance snapshots in
                bulk and cannot be undone through this server.
        """
        rows: list[BalanceHistoryRow] = []
        reader = csv.DictReader(io.StringIO(csv_data))
        for row in reader:
            # Normalize keys to lowercase for case-insensitive matching
            # (SDK uses "Date", "Amount", "Account Name"; users may use lowercase)
            norm = {k.lower().strip(): v for k, v in row.items() if k is not None}

            date_str = norm.get("date")
            if not date_str:
                raise ValidationError("CSV must have a 'date' column")

            amount_str = norm.get("amount") or norm.get("balance")
            if amount_str is None:
                raise ValidationError("CSV must have an 'amount' or 'balance' column")

            try:
                rows.append(
                    BalanceHistoryRow(
                        date=datetime.strptime(date_str.strip(), "%Y-%m-%d"),
                        amount=float(amount_str),
                        account_name=norm.get("account_name")
                        or norm.get("account name"),
                    )
                )
            except ValueError as e:
                raise ValidationError(f"Invalid data in CSV row: {e}")

        if not rows:
            raise ValidationError("csv_data contains no valid rows")

        client = await get_monarch_client()
        await client.upload_account_balance_history(
            account_id, rows, timeout=timeout, delay=delay
        )
        return {"uploaded": True, "account_id": account_id, "rows": len(rows)}
