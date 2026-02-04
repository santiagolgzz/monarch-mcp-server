"""
Transaction management tools for Monarch Money.

Tools for viewing, searching, and managing transactions.
"""

import json
import logging

from fastmcp import FastMCP

from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.safety import require_safety_check
from monarch_mcp_server.utils import validate_date_format, validate_non_empty_string

from ._common import MAX_AGGREGATION_TRANSACTIONS, tool_handler

logger = logging.getLogger(__name__)


def register_transaction_tools(mcp: FastMCP) -> None:
    """Register transaction management tools with the FastMCP instance."""

    @mcp.tool()
    @tool_handler("get_transactions")
    async def get_transactions(
        limit: int = 100,
        offset: int = 0,
        start_date: str | None = None,
        end_date: str | None = None,
        account_id: str | None = None,
        category_id: str | None = None,
        search: str | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
    ) -> list[dict]:
        """Get transactions from Monarch Money with granular filtering."""
        validated_start = validate_date_format(start_date, "start_date")
        validated_end = validate_date_format(end_date, "end_date")

        client = await get_monarch_client()
        filters = {}
        if validated_start:
            filters["start_date"] = validated_start
        if validated_end:
            filters["end_date"] = validated_end
        if account_id:
            filters["account_ids"] = [account_id]
        if category_id:
            filters["category_ids"] = [category_id]
        if search:
            filters["search"] = search

        transactions = await client.get_transactions(
            limit=limit, offset=offset, **filters
        )
        transaction_list = []
        for txn in transactions.get("allTransactions", {}).get("results", []):
            amount = txn.get("amount")

            # Client-side filtering for amount range
            if min_amount is not None and amount is not None and amount < min_amount:
                continue
            if max_amount is not None and amount is not None and amount > max_amount:
                continue

            transaction_info = {
                "id": txn.get("id"),
                "date": txn.get("date"),
                "amount": amount,
                "description": txn.get("description"),
                "category": txn.get("category", {}).get("name")
                if txn.get("category")
                else None,
                "account": txn.get("account", {}).get("displayName"),
                "merchant": txn.get("merchant", {}).get("name")
                if txn.get("merchant")
                else None,
                "is_pending": txn.get("isPending", False),
            }
            transaction_list.append(transaction_info)
        return transaction_list

    @mcp.tool()
    @tool_handler("search_transactions")
    async def search_transactions(query: str, limit: int = 20) -> list[dict]:
        """
        Search for transactions using a keyword search.

        Args:
            query: The search term to find in merchants, categories, or notes.
            limit: Maximum number of results to return (default: 20).
        """
        client = await get_monarch_client()
        transactions = await client.get_transactions(search=query, limit=limit)

        transaction_list = []
        for txn in transactions.get("allTransactions", {}).get("results", []):
            transaction_info = {
                "id": txn.get("id"),
                "date": txn.get("date"),
                "amount": txn.get("amount"),
                "description": txn.get("description"),
                "category": txn.get("category", {}).get("name")
                if txn.get("category")
                else None,
                "merchant": txn.get("merchant", {}).get("name")
                if txn.get("merchant")
                else None,
            }
            transaction_list.append(transaction_info)
        return transaction_list

    @mcp.tool()
    @tool_handler("get_transaction_stats")
    async def get_transaction_stats(
        start_date: str | None = None,
        end_date: str | None = None,
        category_id: str | None = None,
        account_id: str | None = None,
    ) -> dict:
        """
        Get high-level statistics for transactions (sum, count, etc.) without listing them.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            category_id: Optional category ID to filter by.
            account_id: Optional account ID to filter by.
        """
        validated_start = validate_date_format(start_date, "start_date")
        validated_end = validate_date_format(end_date, "end_date")

        client = await get_monarch_client()
        filters = {}
        if validated_start:
            filters["start_date"] = validated_start
        if validated_end:
            filters["end_date"] = validated_end
        if account_id:
            filters["account_ids"] = [account_id]
        if category_id:
            filters["category_ids"] = [category_id]

        # Fetch all transactions matching filters (up to limit for aggregation)
        transactions = await client.get_transactions(
            limit=MAX_AGGREGATION_TRANSACTIONS, **filters
        )
        results = transactions.get("allTransactions", {}).get("results", [])

        count = len(results)
        sum_income = sum(
            txn.get("amount", 0) for txn in results if txn.get("amount", 0) > 0
        )
        sum_expense = sum(
            txn.get("amount", 0) for txn in results if txn.get("amount", 0) < 0
        )
        net = sum_income + sum_expense

        return {
            "count": count,
            "sum_income": round(sum_income, 2),
            "sum_expense": round(sum_expense, 2),
            "net": round(net, 2),
            "currency": "USD",  # Standard for Monarch
            "period": {"start": validated_start, "end": validated_end},
        }

    @mcp.tool()
    @tool_handler("get_transaction_details")
    async def get_transaction_details(transaction_id: str) -> dict:
        """Get detailed information about a specific transaction."""
        client = await get_monarch_client()
        return await client.get_transaction_details(transaction_id)

    @mcp.tool()
    @tool_handler("get_transaction_splits")
    async def get_transaction_splits(transaction_id: str) -> dict:
        """Get split information for a transaction."""
        client = await get_monarch_client()
        return await client.get_transaction_splits(transaction_id)

    @mcp.tool()
    @tool_handler("get_transactions_summary")
    async def get_transactions_summary(
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Get aggregated transaction summary data."""
        validated_start = validate_date_format(start_date, "start_date")
        validated_end = validate_date_format(end_date, "end_date")

        client = await get_monarch_client()
        filters = {}
        if validated_start:
            filters["start_date"] = validated_start
        if validated_end:
            filters["end_date"] = validated_end

        return await client.get_transactions_summary(**filters)

    @mcp.tool()
    @tool_handler("get_recurring_transactions")
    async def get_recurring_transactions() -> dict:
        """Get all recurring transactions."""
        client = await get_monarch_client()
        return await client.get_recurring_transactions()

    # ========== WRITE TOOLS ==========

    @mcp.tool()
    @require_safety_check("create_transaction")
    @tool_handler("create_transaction")
    async def create_transaction(
        account_id: str,
        amount: float,
        merchant_name: str,
        category_id: str,
        date: str,
        notes: str | None = None,
    ) -> dict:
        """Create a new transaction in Monarch Money."""
        validate_non_empty_string(account_id, "account_id")
        validate_non_empty_string(merchant_name, "merchant_name")
        validate_non_empty_string(category_id, "category_id")
        validate_non_empty_string(date, "date")
        validated_date = validate_date_format(date, "date")
        # validated_date is guaranteed non-None after validation
        assert validated_date is not None

        client = await get_monarch_client()
        return await client.create_transaction(
            date=validated_date,
            account_id=account_id,
            amount=amount,
            merchant_name=merchant_name,
            category_id=category_id,
            notes=notes or "",
        )

    @mcp.tool()
    @require_safety_check("update_transaction")
    @tool_handler("update_transaction")
    async def update_transaction(
        transaction_id: str,
        amount: float | None = None,
        description: str | None = None,
        category_id: str | None = None,
        date: str | None = None,
    ) -> dict:
        """Update an existing transaction in Monarch Money."""
        validate_non_empty_string(transaction_id, "transaction_id")
        validated_date = validate_date_format(date, "date") if date else None

        client = await get_monarch_client()

        # Build kwargs dict, excluding None values to avoid overwriting existing data
        update_data: dict[str, str | float] = {}
        if amount is not None:
            update_data["amount"] = amount
        if description is not None:
            update_data["merchant_name"] = description
        if category_id is not None:
            update_data["category_id"] = category_id
        if validated_date is not None:
            update_data["date"] = validated_date

        return await client.update_transaction(
            transaction_id=transaction_id, **update_data
        )  # type: ignore[arg-type]

    @mcp.tool()
    @require_safety_check("delete_transaction")
    @tool_handler("delete_transaction")
    async def delete_transaction(transaction_id: str) -> dict:
        """Delete a transaction from Monarch Money."""
        validate_non_empty_string(transaction_id, "transaction_id")
        client = await get_monarch_client()
        result = await client.delete_transaction(transaction_id)
        # SDK may return bool
        if isinstance(result, bool):
            return {"deleted": result, "transaction_id": transaction_id}
        return result

    @mcp.tool()
    @require_safety_check("update_transaction_splits")
    @tool_handler("update_transaction_splits")
    async def update_transaction_splits(transaction_id: str, splits_data: str) -> dict:
        """Update or create transaction splits."""
        client = await get_monarch_client()
        splits = json.loads(splits_data)
        return await client.update_transaction_splits(transaction_id, splits)
