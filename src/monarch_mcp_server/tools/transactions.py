"""
Transaction management tools for Monarch Money.

Tools for viewing, searching, and managing transactions.
"""

import base64
import binascii
import json
import logging
from dataclasses import dataclass

from fastmcp import FastMCP

from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.exceptions import ValidationError
from monarch_mcp_server.safety import require_safety_check
from monarch_mcp_server.utils import validate_date_format, validate_non_empty_string

from ._common import (
    MAX_AGGREGATION_TRANSACTIONS,
    MAX_ATTACHMENT_BYTES,
    annotated_tool,
    tool_handler,
)

logger = logging.getLogger(__name__)


@dataclass
class _TransactionFilters:
    start_date: str | None = None
    end_date: str | None = None
    account_ids: list[str] | None = None
    category_ids: list[str] | None = None
    search: str = ""


def _build_transaction_filters(
    validated_start: str | None = None,
    validated_end: str | None = None,
    account_id: str | None = None,
    category_id: str | None = None,
    search: str | None = None,
) -> _TransactionFilters:
    """Build Monarch transaction filters, skipping empty values."""
    return _TransactionFilters(
        start_date=validated_start,
        end_date=validated_end,
        account_ids=[account_id] if account_id else None,
        category_ids=[category_id] if category_id else None,
        search=search or "",
    )


def _map_transaction(
    txn: dict, include_account: bool = False, include_pending: bool = False
) -> dict:
    """Normalize a Monarch transaction object to MCP response shape."""
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
    if include_account:
        transaction_info["account"] = txn.get("account", {}).get("displayName")
    if include_pending:
        transaction_info["is_pending"] = txn.get("isPending", False)
    return transaction_info


def register_transaction_tools(mcp: FastMCP) -> None:
    """Register transaction management tools with the FastMCP instance."""

    # ========== LIGHTWEIGHT READ TOOLS (aggregates, summaries) ==========

    @annotated_tool(mcp)
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
        filters = _build_transaction_filters(
            validated_start=validated_start,
            validated_end=validated_end,
            account_id=account_id,
            category_id=category_id,
        )

        # Fetch all transactions matching filters (up to limit for aggregation)
        transactions = await client.get_transactions(
            limit=MAX_AGGREGATION_TRANSACTIONS,
            start_date=filters.start_date,
            end_date=filters.end_date,
            account_ids=filters.account_ids or [],
            category_ids=filters.category_ids or [],
            search=filters.search,
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

    @annotated_tool(mcp)
    @tool_handler("get_transactions_summary")
    async def get_transactions_summary() -> dict:
        """Get aggregated transaction summary data across the whole account.

        This summary is not date-filterable: the underlying SDK call takes no
        arguments. For aggregates over a date range, use get_transaction_stats,
        which accepts start_date and end_date.
        """
        client = await get_monarch_client()
        return await client.get_transactions_summary()

    @annotated_tool(mcp)
    @tool_handler("get_recurring_transactions")
    async def get_recurring_transactions(
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Get recurring transactions, optionally limited to a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
        """
        validated_start = validate_date_format(start_date, "start_date")
        validated_end = validate_date_format(end_date, "end_date")

        client = await get_monarch_client()
        return await client.get_recurring_transactions(
            start_date=validated_start,
            end_date=validated_end,
        )

    @annotated_tool(mcp)
    @tool_handler("get_cashflow")
    async def get_cashflow(
        limit: int = 100,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Get cashflow data with income and expense breakdowns.

        Args:
            limit: Maximum number of results (default: 100).
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
        """
        validated_start = validate_date_format(start_date, "start_date")
        validated_end = validate_date_format(end_date, "end_date")
        client = await get_monarch_client()
        return await client.get_cashflow(
            limit=limit, start_date=validated_start, end_date=validated_end
        )

    @annotated_tool(mcp)
    @tool_handler("get_cashflow_summary")
    async def get_cashflow_summary(
        limit: int = 100,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Get aggregated cashflow summary totals.

        Args:
            limit: Maximum number of results (default: 100).
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
        """
        validated_start = validate_date_format(start_date, "start_date")
        validated_end = validate_date_format(end_date, "end_date")
        client = await get_monarch_client()
        return await client.get_cashflow_summary(
            limit=limit, start_date=validated_start, end_date=validated_end
        )

    # ========== TARGETED READ TOOLS (search, filtered lists) ==========

    @annotated_tool(mcp)
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
            transaction_list.append(_map_transaction(txn))
        return transaction_list

    @annotated_tool(mcp)
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
        tag_ids: list[str] | None = None,
        has_attachments: bool | None = None,
        has_notes: bool | None = None,
        hidden_from_reports: bool | None = None,
        is_split: bool | None = None,
        is_recurring: bool | None = None,
        imported_from_mint: bool | None = None,
        synced_from_institution: bool | None = None,
    ) -> list[dict]:
        """Get transactions from Monarch Money with granular filtering.

        Args:
            limit: Maximum number of transactions to return.
            offset: Number of transactions to skip (for pagination).
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            account_id: Only transactions on this account.
            category_id: Only transactions in this category.
            search: Free-text search over merchant and description.
            min_amount: Drop transactions below this amount (applied locally).
            max_amount: Drop transactions above this amount (applied locally).
            tag_ids: Only transactions carrying any of these tag IDs.
            has_attachments: True for only transactions with attachments,
                False for only those without. None does not filter.
            has_notes: True/False to require or exclude notes. None does not filter.
            hidden_from_reports: True/False to select transactions hidden from
                reports. None does not filter.
            is_split: True/False to select split transactions. None does not filter.
            is_recurring: True/False to select recurring transactions. None does
                not filter.
            imported_from_mint: True/False to select transactions imported from
                Mint. None does not filter.
            synced_from_institution: True/False to select transactions synced
                from a linked institution rather than entered manually. None
                does not filter.
        """
        validated_start = validate_date_format(start_date, "start_date")
        validated_end = validate_date_format(end_date, "end_date")

        client = await get_monarch_client()
        filters = _build_transaction_filters(
            validated_start=validated_start,
            validated_end=validated_end,
            account_id=account_id,
            category_id=category_id,
            search=search,
        )

        transactions = await client.get_transactions(
            limit=limit,
            offset=offset,
            start_date=filters.start_date,
            end_date=filters.end_date,
            account_ids=filters.account_ids or [],
            category_ids=filters.category_ids or [],
            search=filters.search,
            tag_ids=tag_ids or [],
            has_attachments=has_attachments,
            has_notes=has_notes,
            hidden_from_reports=hidden_from_reports,
            is_split=is_split,
            is_recurring=is_recurring,
            imported_from_mint=imported_from_mint,
            synced_from_institution=synced_from_institution,
        )
        transaction_list = []
        for txn in transactions.get("allTransactions", {}).get("results", []):
            amount = txn.get("amount")

            # Client-side filtering for amount range
            if min_amount is not None and amount is not None and amount < min_amount:
                continue
            if max_amount is not None and amount is not None and amount > max_amount:
                continue

            transaction_info = _map_transaction(
                txn, include_account=True, include_pending=True
            )
            transaction_info["amount"] = amount
            transaction_list.append(transaction_info)
        return transaction_list

    @annotated_tool(mcp)
    @tool_handler("get_transaction_details")
    async def get_transaction_details(
        transaction_id: str,
        redirect_posted: bool = True,
    ) -> dict:
        """Get detailed information about a specific transaction.

        Args:
            transaction_id: The transaction to look up.
            redirect_posted: When a pending transaction has since posted,
                follow the redirect to the posted transaction. Defaults to
                True, matching the SDK and the Monarch app.
        """
        client = await get_monarch_client()
        return await client.get_transaction_details(
            transaction_id, redirect_posted=redirect_posted
        )

    @annotated_tool(mcp)
    @tool_handler("get_transaction_splits")
    async def get_transaction_splits(transaction_id: str) -> dict:
        """Get split information for a transaction."""
        client = await get_monarch_client()
        return await client.get_transaction_splits(transaction_id)

    # ========== WRITE TOOLS ==========

    @annotated_tool(mcp)
    @require_safety_check("upload_attachment")
    @tool_handler("upload_attachment")
    async def upload_attachment(
        transaction_id: str,
        file_content_base64: str,
        filename: str,
    ) -> dict:
        """Attach a file to a transaction, such as a receipt.

        MCP carries text, not raw bytes, so the file must be base64-encoded.

        Args:
            transaction_id: The transaction to attach the file to.
            file_content_base64: The file's bytes, base64-encoded.
            filename: File name including extension, e.g. "receipt.pdf". The
                extension determines the content type Monarch stores.
        """
        validate_non_empty_string(transaction_id, "transaction_id")
        validate_non_empty_string(filename, "filename")
        validate_non_empty_string(file_content_base64, "file_content_base64")

        try:
            file_bytes = base64.b64decode(file_content_base64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValidationError(
                f"file_content_base64 is not valid base64: {e}"
            ) from e

        # No empty-file check is needed: the only base64 string that decodes to
        # zero bytes is the empty string, which validate_non_empty_string above
        # has already rejected.
        if len(file_bytes) > MAX_ATTACHMENT_BYTES:
            raise ValidationError(
                f"Attachment is {len(file_bytes)} bytes, over the "
                f"{MAX_ATTACHMENT_BYTES} byte limit"
            )

        client = await get_monarch_client()
        result = await client.upload_attachment(
            transaction_id=transaction_id,
            file_content=file_bytes,
            filename=filename,
        )
        return {
            "uploaded": True,
            "transaction_id": transaction_id,
            "filename": filename,
            "bytes": len(file_bytes),
            "result": result,
        }

    @annotated_tool(mcp)
    @require_safety_check("create_transaction")
    @tool_handler("create_transaction")
    async def create_transaction(
        account_id: str,
        amount: float,
        merchant_name: str,
        category_id: str,
        date: str,
        notes: str | None = None,
        update_balance: bool = False,
    ) -> dict:
        """Create a new transaction in Monarch Money.

        Set update_balance=True to have the transaction change the account's
        balance (same as the "impact balance" checkbox in the Monarch app).
        Defaults to False, which leaves the balance unchanged.
        """
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
            update_balance=update_balance,
        )

    @annotated_tool(mcp)
    @require_safety_check("update_transaction")
    @tool_handler("update_transaction")
    async def update_transaction(
        transaction_id: str,
        amount: float | None = None,
        description: str | None = None,
        category_id: str | None = None,
        date: str | None = None,
        goal_id: str | None = None,
        hide_from_reports: bool | None = None,
        needs_review: bool | None = None,
        notes: str | None = None,
    ) -> dict:
        """Update an existing transaction in Monarch Money.

        Every field is optional; omitting one leaves it unchanged. The SDK
        treats None as "do not update" for all of these, so they are passed
        through directly rather than being filtered out here.

        Args:
            transaction_id: The transaction to update.
            amount: New amount.
            description: New merchant name.
            category_id: New category.
            date: New date, YYYY-MM-DD.
            goal_id: Link the transaction to this goal.
            hide_from_reports: Hide or unhide this transaction from reports.
            needs_review: Mark the transaction as needing review, or clear it.
            notes: Replace the transaction's notes.
        """
        validate_non_empty_string(transaction_id, "transaction_id")
        validated_date = validate_date_format(date, "date") if date else None

        client = await get_monarch_client()
        return await client.update_transaction(
            transaction_id=transaction_id,
            amount=amount,
            merchant_name=description,
            category_id=category_id,
            date=validated_date,
            goal_id=goal_id,
            hide_from_reports=hide_from_reports,
            needs_review=needs_review,
            notes=notes,
        )

    @annotated_tool(mcp)
    @require_safety_check("categorize_transaction")
    @tool_handler("categorize_transaction")
    async def categorize_transaction(transaction_id: str, category_id: str) -> dict:
        """Assign a category to a transaction."""
        validate_non_empty_string(transaction_id, "transaction_id")
        validate_non_empty_string(category_id, "category_id")
        client = await get_monarch_client()
        return await client.update_transaction(
            transaction_id=transaction_id, category_id=category_id
        )

    @annotated_tool(mcp)
    @require_safety_check("delete_transaction")
    @tool_handler("delete_transaction")
    async def delete_transaction(
        transaction_id: str,
        confirmation_token: str | None = None,
    ) -> dict:
        """Delete a transaction from Monarch Money.

        Args:
            transaction_id: The transaction to delete.
            confirmation_token: Leave unset on the first call. The server
                replies with a token and a description of what will be
                destroyed; repeat the call with that token to carry it out.
                The token works once, only for these exact arguments, and
                expires.
        """
        validate_non_empty_string(transaction_id, "transaction_id")
        client = await get_monarch_client()
        result = await client.delete_transaction(transaction_id)
        # SDK may return bool
        if isinstance(result, bool):
            return {"deleted": result, "transaction_id": transaction_id}
        return result

    @annotated_tool(mcp)
    @require_safety_check("update_transaction_splits")
    @tool_handler("update_transaction_splits")
    async def update_transaction_splits(transaction_id: str, splits_data: str) -> dict:
        """Update or create transaction splits."""
        client = await get_monarch_client()
        splits = json.loads(splits_data)
        return await client.update_transaction_splits(transaction_id, splits)
