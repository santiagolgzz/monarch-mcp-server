"""
HTTP server with GitHub OAuth for Monarch Money MCP Server.

This module enables hosting the MCP server online for use with Claude mobile app
and other remote MCP clients. It wraps the server with:
- GitHub OAuth authentication (RFC-compliant)
- SSE/Streamable HTTP transport for MCP protocol
- Health check endpoint for monitoring

Usage:
    # Set required environment variables:
    export GITHUB_CLIENT_ID="your-github-client-id"
    export GITHUB_CLIENT_SECRET="your-github-client-secret"
    export MONARCH_TOKEN="your-monarch-token"  # From login_setup.py

    # Run the server:
    python -m monarch_mcp_server.http_server

    # Or with uvicorn directly:
    uvicorn monarch_mcp_server.http_server:app --host 0.0.0.0 --port 8000
"""

import os
import logging
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, Mount

from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_base_url() -> str:
    """Get the base URL for the server."""
    # Allow explicit override
    if base_url := os.getenv("BASE_URL"):
        return base_url.rstrip("/")

    # Railway sets PORT and provides a domain
    port = os.getenv("PORT", "8000")

    # Check for Railway's automatic domain
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if railway_domain:
        return f"https://{railway_domain}"

    # Check for Google Cloud Run
    cloud_run_service = os.getenv("K_SERVICE")
    cloud_run_region = os.getenv("CLOUD_RUN_REGION", "us-central1")
    gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    if cloud_run_service and gcp_project:
        return f"https://{cloud_run_service}-{gcp_project}.{cloud_run_region}.run.app"

    # Local development
    host = os.getenv("HOST", "localhost")
    return f"http://{host}:{port}"


def create_mcp_server() -> FastMCP:
    """Create the FastMCP server with GitHub OAuth and all Monarch tools."""

    base_url = get_base_url()
    client_id = os.getenv("GITHUB_CLIENT_ID", "")
    client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        logger.warning("GitHub OAuth credentials not set - server will fail auth requests")

    # Create GitHub OAuth provider
    github_auth = GitHubProvider(
        client_id=client_id,
        client_secret=client_secret,
        base_url=base_url,
        redirect_path="/auth/callback",
        # Don't require consent screen for personal use
        require_authorization_consent=False,
    )

    # Create FastMCP server with auth
    mcp = FastMCP(
        "Monarch Money MCP Server",
        auth=github_auth,
        instructions="MCP server for Monarch Money personal finance management",
    )

    # Import and register all tools from the original server
    _register_monarch_tools(mcp)

    return mcp


def _register_monarch_tools(mcp: FastMCP) -> None:
    """Register all Monarch Money tools with the FastMCP server."""

    # Import dependencies
    import json
    from monarch_mcp_server.secure_session import secure_session
    from monarch_mcp_server.safety import get_safety_guard, require_safety_check
    from monarch_mcp_server.utils import (
        run_async,
        format_error,
        validate_date_format,
        validate_non_empty_string,
        validate_positive_amount,
    )
    from monarch_mcp_server.exceptions import ValidationError
    from monarchmoney import MonarchMoney, MonarchMoneyEndpoints

    # Apply the API URL patch
    MonarchMoneyEndpoints.BASE_URL = "https://api.monarch.com"

    async def get_monarch_client() -> MonarchMoney:
        """Get or create MonarchMoney client instance."""
        client = secure_session.get_authenticated_client()
        if client is not None:
            return client

        email = os.getenv("MONARCH_EMAIL")
        password = os.getenv("MONARCH_PASSWORD")

        if email and password:
            client = MonarchMoney()
            mfa_secret = os.getenv("MONARCH_MFA_SECRET")
            await client.login(email, password, mfa_secret_key=mfa_secret)
            secure_session.save_authenticated_session(client)
            return client

        raise RuntimeError("Authentication needed! Set MONARCH_TOKEN env var.")

    # ========== READ-ONLY TOOLS ==========

    @mcp.tool()
    def get_accounts() -> str:
        """Get all financial accounts from Monarch Money."""
        try:
            async def _get_accounts():
                client = await get_monarch_client()
                return await client.get_accounts()

            accounts = run_async(_get_accounts())
            account_list = []
            for account in accounts.get("accounts", []):
                account_info = {
                    "id": account.get("id"),
                    "name": account.get("displayName") or account.get("name"),
                    "type": (account.get("type") or {}).get("name"),
                    "balance": account.get("currentBalance"),
                    "institution": (account.get("institution") or {}).get("name"),
                    "is_active": account.get("isActive") if "isActive" in account else not account.get("deactivatedAt"),
                }
                account_list.append(account_info)
            return json.dumps(account_list, indent=2, default=str)
        except Exception as e:
            return format_error(e, "get_accounts")

    @mcp.tool()
    def get_account_holdings(account_id: str) -> str:
        """Get investment holdings for a specific account."""
        try:
            async def _get_holdings():
                client = await get_monarch_client()
                return await client.get_account_holdings(account_id)

            holdings = run_async(_get_holdings())
            return json.dumps(holdings, indent=2, default=str)
        except Exception as e:
            return f"Error getting account holdings: {str(e)}"

    @mcp.tool()
    def get_account_history(
        account_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """Get daily account balance history for a specific account."""
        try:
            async def _get_history():
                client = await get_monarch_client()
                history = await client.get_account_history(account_id=account_id)

                # Client-side filtering since SDK doesn't support date params
                if start_date or end_date:
                    filtered_history = []
                    for entry in history:
                        entry_date = entry.get("date")
                        if not entry_date:
                            filtered_history.append(entry)
                            continue
                        if start_date and entry_date < start_date:
                            continue
                        if end_date and entry_date > end_date:
                            continue
                        filtered_history.append(entry)
                    return filtered_history

                return history

            history = run_async(_get_history())
            return json.dumps(history, indent=2, default=str)
        except Exception as e:
            return f"Error getting account history: {str(e)}"

    @mcp.tool()
    def get_transactions(
        limit: int = 100,
        offset: int = 0,
        start_date: str | None = None,
        end_date: str | None = None,
        account_id: str | None = None,
    ) -> str:
        """Get transactions from Monarch Money."""
        try:
            validated_start = validate_date_format(start_date, "start_date")
            validated_end = validate_date_format(end_date, "end_date")

            async def _get_transactions():
                client = await get_monarch_client()
                filters = {}
                if validated_start:
                    filters["start_date"] = validated_start
                if validated_end:
                    filters["end_date"] = validated_end
                if account_id:
                    filters["account_id"] = account_id
                return await client.get_transactions(limit=limit, offset=offset, **filters)

            transactions = run_async(_get_transactions())
            transaction_list = []
            for txn in transactions.get("allTransactions", {}).get("results", []):
                transaction_info = {
                    "id": txn.get("id"),
                    "date": txn.get("date"),
                    "amount": txn.get("amount"),
                    "description": txn.get("description"),
                    "category": txn.get("category", {}).get("name") if txn.get("category") else None,
                    "account": txn.get("account", {}).get("displayName"),
                    "merchant": txn.get("merchant", {}).get("name") if txn.get("merchant") else None,
                    "is_pending": txn.get("isPending", False),
                }
                transaction_list.append(transaction_info)
            return json.dumps(transaction_list, indent=2, default=str)
        except Exception as e:
            return format_error(e, "get_transactions")

    @mcp.tool()
    def get_transactions_summary() -> str:
        """Get aggregated transaction summary data."""
        try:
            async def _get_summary():
                client = await get_monarch_client()
                return await client.get_transactions_summary()

            summary = run_async(_get_summary())
            return json.dumps(summary, indent=2, default=str)
        except Exception as e:
            return f"Error getting transactions summary: {str(e)}"

    @mcp.tool()
    def get_budgets() -> str:
        """Get budget information from Monarch Money."""
        try:
            async def _get_budgets():
                client = await get_monarch_client()
                return await client.get_budgets()

            budgets = run_async(_get_budgets())
            budget_list = []
            for budget in budgets.get("budgets", []):
                budget_info = {
                    "id": budget.get("id"),
                    "name": budget.get("name"),
                    "amount": budget.get("amount"),
                    "spent": budget.get("spent"),
                    "remaining": budget.get("remaining"),
                    "category": budget.get("category", {}).get("name"),
                    "period": budget.get("period"),
                }
                budget_list.append(budget_info)
            return json.dumps(budget_list, indent=2, default=str)
        except Exception as e:
            return f"Error getting budgets: {str(e)}"

    @mcp.tool()
    def get_transaction_categories() -> str:
        """Get all transaction categories from Monarch Money with their IDs."""
        try:
            async def _get_categories():
                client = await get_monarch_client()
                return await client.get_transaction_categories()

            categories = run_async(_get_categories())
            category_list = []
            for cat in categories.get("categories", []):
                category_info = {
                    "id": cat.get("id"),
                    "name": cat.get("name"),
                    "icon": cat.get("icon"),
                    "group": cat.get("group", {}).get("name") if cat.get("group") else None,
                }
                category_list.append(category_info)
            return json.dumps(category_list, indent=2, default=str)
        except Exception as e:
            return f"Error getting transaction categories: {str(e)}"

    @mcp.tool()
    def get_cashflow(start_date: str | None = None, end_date: str | None = None) -> str:
        """Get cashflow analysis from Monarch Money."""
        try:
            async def _get_cashflow():
                client = await get_monarch_client()
                filters = {}
                if start_date:
                    filters["start_date"] = start_date
                if end_date:
                    filters["end_date"] = end_date
                return await client.get_cashflow(**filters)

            cashflow = run_async(_get_cashflow())
            return json.dumps(cashflow, indent=2, default=str)
        except Exception as e:
            return f"Error getting cashflow: {str(e)}"

    @mcp.tool()
    def get_cashflow_summary(
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """Get aggregated cashflow summary data."""
        try:
            async def _get_summary():
                client = await get_monarch_client()
                filters = {}
                if start_date:
                    filters["start_date"] = start_date
                if end_date:
                    filters["end_date"] = end_date
                return await client.get_cashflow_summary(**filters)

            summary = run_async(_get_summary())
            return json.dumps(summary, indent=2, default=str)
        except Exception as e:
            return f"Error getting cashflow summary: {str(e)}"

    @mcp.tool()
    def get_subscription_details() -> str:
        """Get Monarch Money subscription details (account status, paid/trial)."""
        try:
            async def _get_subscription():
                client = await get_monarch_client()
                return await client.get_subscription_details()

            subscription = run_async(_get_subscription())
            return json.dumps(subscription, indent=2, default=str)
        except Exception as e:
            return f"Error getting subscription details: {str(e)}"

    @mcp.tool()
    def is_accounts_refresh_complete() -> str:
        """Check if account refresh/synchronization is complete."""
        try:
            async def _check_refresh():
                client = await get_monarch_client()
                return await client.is_accounts_refresh_complete()

            result = run_async(_check_refresh())
            return json.dumps({"refresh_complete": result}, indent=2, default=str)
        except Exception as e:
            return f"Error checking refresh status: {str(e)}"

    @mcp.tool()
    def refresh_accounts() -> str:
        """Request account data refresh from financial institutions."""
        try:
            async def _refresh_accounts():
                client = await get_monarch_client()
                return await client.request_accounts_refresh()

            result = run_async(_refresh_accounts())
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error refreshing accounts: {str(e)}"

    @mcp.tool()
    def request_accounts_refresh_and_wait() -> str:
        """Request account refresh and wait for completion (blocking operation)."""
        try:
            async def _refresh_and_wait():
                client = await get_monarch_client()
                return await client.request_accounts_refresh_and_wait()

            result = run_async(_refresh_and_wait())
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error refreshing and waiting: {str(e)}"

    # ========== WRITE TOOLS (with safety decorator) ==========

    @mcp.tool()
    @require_safety_check("create_transaction")
    def create_transaction(
        account_id: str,
        amount: float,
        merchant_name: str,
        category_id: str,
        date: str,
        notes: str | None = None,
    ) -> str:
        """
        Create a new transaction in Monarch Money.

        Args:
            account_id: The account ID to add the transaction to
            amount: Transaction amount (positive for income, negative for expenses)
            merchant_name: Merchant name for the transaction
            category_id: Category ID for the transaction
            date: Transaction date in YYYY-MM-DD format
            notes: Optional notes for the transaction

        Safety: Rate limited, logged for rollback
        """
        try:
            validate_non_empty_string(account_id, "account_id")
            validate_non_empty_string(merchant_name, "merchant_name")
            validate_non_empty_string(category_id, "category_id")
            validated_date = validate_date_format(date, "date")

            async def _create_transaction():
                client = await get_monarch_client()
                transaction_data = {
                    "account_id": account_id,
                    "amount": amount,
                    "merchant_name": merchant_name,
                    "category_id": category_id,
                    "date": validated_date,
                    "notes": notes or "",
                }
                return await client.create_transaction(**transaction_data)

            result = run_async(_create_transaction())
            return json.dumps(result, indent=2, default=str)
        except ValidationError as e:
            return format_error(e, "create_transaction")
        except Exception as e:
            return format_error(e, "create_transaction")

    @mcp.tool()
    @require_safety_check("update_transaction")
    def update_transaction(
        transaction_id: str,
        amount: float | None = None,
        description: str | None = None,
        category_id: str | None = None,
        date: str | None = None,
    ) -> str:
        """
        Update an existing transaction in Monarch Money.

        Args:
            transaction_id: The ID of the transaction to update
            amount: New transaction amount
            description: New transaction description
            category_id: New category ID
            date: New transaction date in YYYY-MM-DD format

        Safety: Rate limited, logged for rollback
        """
        try:
            validate_non_empty_string(transaction_id, "transaction_id")
            validated_date = validate_date_format(date, "date") if date else None

            async def _update_transaction():
                client = await get_monarch_client()
                update_data = {"transaction_id": transaction_id}
                if amount is not None:
                    update_data["amount"] = amount
                if description is not None:
                    update_data["description"] = description
                if category_id is not None:
                    update_data["category_id"] = category_id
                if validated_date is not None:
                    update_data["date"] = validated_date
                return await client.update_transaction(**update_data)

            result = run_async(_update_transaction())
            return json.dumps(result, indent=2, default=str)
        except ValidationError as e:
            return format_error(e, "update_transaction")
        except Exception as e:
            return format_error(e, "update_transaction")

    @mcp.tool()
    @require_safety_check("delete_transaction")
    def delete_transaction(transaction_id: str) -> str:
        """
        Delete a transaction from Monarch Money.

        Args:
            transaction_id: The ID of the transaction to delete

        Safety: HIGH RISK - Requires approval, logged for rollback
        """
        try:
            async def _delete_transaction():
                client = await get_monarch_client()
                return await client.delete_transaction(transaction_id)

            result = run_async(_delete_transaction())
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error deleting transaction: {str(e)}"

    @mcp.tool()
    @require_safety_check("create_transaction_category")
    def create_transaction_category(name: str, group_id: str | None = None) -> str:
        """
        Create a new transaction category.

        Args:
            name: Name of the new category
            group_id: Optional category group ID to assign the category to

        Safety: Rate limited, logged for rollback
        """
        try:
            async def _create_category():
                client = await get_monarch_client()
                if group_id:
                    return await client.create_transaction_category(
                        transaction_category_name=name, group_id=group_id
                    )
                return await client.create_transaction_category(
                    transaction_category_name=name, group_id=group_id
                )

            result = run_async(_create_category())
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error creating transaction category: {str(e)}"

    @mcp.tool()
    @require_safety_check("delete_transaction_category")
    def delete_transaction_category(category_id: str) -> str:
        """
        Delete a transaction category.

        Args:
            category_id: The ID of the category to delete

        Safety: HIGH RISK - Requires approval, logged for rollback
        """
        try:
            async def _delete_category():
                client = await get_monarch_client()
                return await client.delete_transaction_category(category_id)

            result = run_async(_delete_category())
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error deleting transaction category: {str(e)}"

    @mcp.tool()
    @require_safety_check("delete_transaction_categories")
    def delete_transaction_categories(category_ids: str) -> str:
        """
        Delete multiple transaction categories.

        Args:
            category_ids: Comma-separated list of category IDs to delete

        Safety: HIGH RISK - Requires approval, logged for rollback
        """
        try:
            async def _delete_categories():
                client = await get_monarch_client()
                ids_list = [id.strip() for id in category_ids.split(",")]
                return await client.delete_transaction_categories(ids_list)

            result = run_async(_delete_categories())
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error deleting transaction categories: {str(e)}"

    @mcp.tool()
    @require_safety_check("create_manual_account")
    def create_manual_account(
        account_name: str,
        account_type: str,
        current_balance: float,
        account_subtype: str | None = None,
    ) -> str:
        """
        Create a manual account (not linked to a financial institution).

        Args:
            account_name: Name of the account
            account_type: Type of account (e.g., 'checking', 'savings', 'credit')
            current_balance: Current account balance
            account_subtype: Optional account subtype

        Safety: Rate limited, logged for rollback
        """
        try:
            validate_non_empty_string(account_name, "account_name")
            validate_non_empty_string(account_type, "account_type")

            async def _create_account():
                client = await get_monarch_client()
                account_data = {
                    "account_name": account_name,
                    "account_type": account_type,
                    "account_balance": current_balance,
                }
                if account_subtype:
                    account_data["account_sub_type"] = account_subtype
                return await client.create_manual_account(**account_data)

            result = run_async(_create_account())
            return json.dumps(result, indent=2, default=str)
        except ValidationError as e:
            return f"Validation error: {str(e)}"
        except Exception as e:
            return f"Error creating manual account: {str(e)}"

    @mcp.tool()
    @require_safety_check("update_account")
    def update_account(
        account_id: str,
        name: str | None = None,
        balance: float | None = None,
        account_type: str | None = None,
    ) -> str:
        """
        Update account settings or balance.

        Args:
            account_id: The ID of the account to update
            name: New account name (optional)
            balance: New account balance (optional)
            account_type: New account type (optional)

        Safety: Rate limited, logged for rollback
        """
        try:
            async def _update_account():
                client = await get_monarch_client()
                update_data = {"account_id": account_id}
                if name is not None:
                    update_data["account_name"] = name
                if balance is not None:
                    update_data["account_balance"] = balance
                if account_type is not None:
                    update_data["account_type"] = account_type
                return await client.update_account(**update_data)

            result = run_async(_update_account())
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error updating account: {str(e)}"

    @mcp.tool()
    @require_safety_check("delete_account")
    def delete_account(account_id: str) -> str:
        """
        Delete an account from Monarch Money.

        Args:
            account_id: The ID of the account to delete

        Safety: HIGH RISK - Requires approval, logged for rollback
        """
        try:
            async def _delete_account():
                client = await get_monarch_client()
                return await client.delete_account(account_id)

            result = run_async(_delete_account())
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error deleting account: {str(e)}"

    @mcp.tool()
    @require_safety_check("create_tag")
    def create_tag(name: str, color: str | None = None) -> str:
        """
        Create a new transaction tag.

        Args:
            name: Name of the new tag
            color: Optional color for the tag (hex format, e.g., '#FF5733')

        Safety: Rate limited, logged for rollback
        """
        try:
            validate_non_empty_string(name, "name")

            async def _create_tag():
                client = await get_monarch_client()
                if color:
                    return await client.create_tag(name=name, color=color)
                return await client.create_tag(name=name)

            result = run_async(_create_tag())
            return json.dumps(result, indent=2, default=str)
        except ValidationError as e:
            return f"Validation error: {str(e)}"
        except Exception as e:
            return f"Error creating tag: {str(e)}"

    @mcp.tool()
    @require_safety_check("set_transaction_tags")
    def set_transaction_tags(transaction_id: str, tag_ids: str) -> str:
        """
        Assign tags to a transaction.

        Args:
            transaction_id: The ID of the transaction
            tag_ids: Comma-separated list of tag IDs to assign

        Safety: Rate limited, logged for rollback
        """
        try:
            async def _set_tags():
                client = await get_monarch_client()
                ids_list = [id.strip() for id in tag_ids.split(",")]
                return await client.set_transaction_tags(transaction_id, ids_list)

            result = run_async(_set_tags())
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error setting transaction tags: {str(e)}"

    @mcp.tool()
    @require_safety_check("update_transaction_splits")
    def update_transaction_splits(transaction_id: str, splits_data: str) -> str:
        """
        Update or create transaction splits.

        Args:
            transaction_id: The ID of the transaction
            splits_data: JSON string containing split information
                         Example: '[{"amount": 50.00, "category_id": "123"}, {"amount": 30.00, "category_id": "456"}]'

        Safety: Rate limited, logged for rollback
        """
        try:
            async def _update_splits():
                client = await get_monarch_client()
                splits = json.loads(splits_data)
                return await client.update_transaction_splits(transaction_id, splits)

            result = run_async(_update_splits())
            return json.dumps(result, indent=2, default=str)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in splits_data: {str(e)}"
        except Exception as e:
            return f"Error updating transaction splits: {str(e)}"

    @mcp.tool()
    @require_safety_check("set_budget_amount")
    def set_budget_amount(category_id: str, amount: float) -> str:
        """
        Set or update budget amount for a category. Set to 0 to clear the budget.

        Args:
            category_id: The ID of the category
            amount: Budget amount (set to 0 to clear budget)

        Safety: Rate limited, logged for rollback
        """
        try:
            async def _set_budget():
                client = await get_monarch_client()
                return await client.set_budget_amount(category_id, amount)

            result = run_async(_set_budget())
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error setting budget amount: {str(e)}"

    @mcp.tool()
    @require_safety_check("upload_account_balance_history")
    def upload_account_balance_history(account_id: str, csv_data: str) -> str:
        """
        Upload account balance history from CSV data.

        Args:
            account_id: The ID of the account
            csv_data: CSV data with date and balance columns
                      Example format:
                      date,balance
                      2024-01-01,1000.00
                      2024-01-02,1050.00

        Safety: HIGH RISK - Requires approval, logged for rollback
        """
        try:
            async def _upload_history():
                client = await get_monarch_client()
                return await client.upload_account_balance_history(account_id, csv_data)

            result = run_async(_upload_history())
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error uploading account balance history: {str(e)}"

    # ========== SAFETY MANAGEMENT TOOLS ==========

    @mcp.tool()
    def get_safety_stats() -> str:
        """Get current safety statistics including rate limits and daily operation counts."""
        try:
            guard = get_safety_guard()
            stats = guard.get_operation_stats()
            return json.dumps(stats, indent=2, default=str)
        except Exception as e:
            return f"Error getting safety stats: {str(e)}"

    @mcp.tool()
    def enable_emergency_stop() -> str:
        """
        EMERGENCY: Disable all write operations immediately.

        Use this if you detect runaway behavior or want to prevent any modifications.
        This will block all create, update, and delete operations until manually disabled.

        To re-enable: Use disable_emergency_stop()
        """
        try:
            guard = get_safety_guard()
            return guard.enable_emergency_stop()
        except Exception as e:
            return f"Error enabling emergency stop: {str(e)}"

    @mcp.tool()
    def disable_emergency_stop() -> str:
        """
        Re-enable write operations after emergency stop.

        This will restore normal operation of all create, update, and delete functions.
        """
        try:
            guard = get_safety_guard()
            return guard.disable_emergency_stop()
        except Exception as e:
            return f"Error disabling emergency stop: {str(e)}"

    @mcp.tool()
    def get_recent_operations(limit: int = 10) -> str:
        """
        View recent write operations with rollback information.

        Shows the last N operations with:
        - Timestamp
        - Operation type
        - Parameters used
        - Rollback suggestions

        Args:
            limit: Number of recent operations to show (default: 10, max: 50)
        """
        try:
            from pathlib import Path

            limit = min(limit, 50)  # Cap at 50
            detailed_log_path = Path.home() / ".mm" / "detailed_operation_log.jsonl"

            if not detailed_log_path.exists():
                return json.dumps(
                    {"message": "No operations logged yet", "operations": []}, indent=2
                )

            # Read last N lines
            operations = []
            with open(detailed_log_path, "r") as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        operations.append(json.loads(line))
                    except:
                        continue

            # Reverse to show most recent first
            operations.reverse()

            return json.dumps(
                {
                    "count": len(operations),
                    "operations": operations,
                    "log_file": str(detailed_log_path),
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return f"Error getting recent operations: {str(e)}"

    @mcp.tool()
    def get_rollback_suggestions(operation_index: int = 0) -> str:
        """
        Get detailed rollback suggestions for a recent operation.

        Args:
            operation_index: Index of operation (0 = most recent, 1 = second most recent, etc.)

        Returns detailed instructions on how to undo/rollback the operation.
        """
        try:
            from pathlib import Path

            detailed_log_path = Path.home() / ".mm" / "detailed_operation_log.jsonl"

            if not detailed_log_path.exists():
                return "No operations logged yet."

            # Read operations
            operations = []
            with open(detailed_log_path, "r") as f:
                for line in f:
                    try:
                        operations.append(json.loads(line))
                    except:
                        continue

            if not operations:
                return "No operations found in log."

            # Get the requested operation (from end, so 0 = most recent)
            if operation_index >= len(operations):
                return f"Operation index {operation_index} not found. Only {len(operations)} operations logged."

            op = operations[-(operation_index + 1)]

            # Generate rollback suggestions
            rollback = op.get("rollback_info", {})
            params = op.get("parameters", {})

            suggestion = f"""🔄 Rollback Information for Operation #{len(operations) - operation_index}

📅 Timestamp: {op.get('timestamp')}
⚙️  Operation: {op.get('operation')}
📝 Parameters: {json.dumps(params, indent=2)}

{'✅ REVERSIBLE' if rollback.get('reversible') else '❌ NOT EASILY REVERSIBLE'}

"""

            if rollback.get("reversible"):
                suggestion += f"""🔄 Reverse Operation: {rollback.get('reverse_operation')}
📋 Instructions: {rollback.get('notes')}

"""

                # Provide specific rollback commands
                if "deleted_id" in rollback:
                    suggestion += f"💡 To undo: Recreate the deleted item using its original details\n"
                    suggestion += f"   Deleted ID: {rollback['deleted_id']}\n"

                elif "deleted_ids" in rollback:
                    suggestion += f"💡 To undo: Recreate {len(rollback['deleted_ids'])} deleted items\n"
                    suggestion += f"   Deleted IDs: {', '.join(rollback['deleted_ids'])}\n"

                elif "created_id" in rollback:
                    suggestion += f"💡 To undo: Delete the created item\n"
                    suggestion += f"   Created ID: {rollback['created_id']}\n"

                elif "modified_id" in rollback and "modified_fields" in rollback:
                    suggestion += f"💡 To undo: Restore original values\n"
                    suggestion += f"   Modified ID: {rollback['modified_id']}\n"
                    suggestion += f"   Changed fields: {', '.join(rollback['modified_fields'].keys())}\n"
                    suggestion += f"   Note: You need the original values to restore\n"

            else:
                suggestion += "⚠️  This operation cannot be easily reversed.\n"
                suggestion += "   You may need to manually fix any issues in Monarch Money web interface.\n"

            return suggestion

        except Exception as e:
            return f"Error getting rollback suggestions: {str(e)}"

    logger.info("Registered 32 Monarch Money tools with FastMCP server")


# Health check endpoint (public, no auth required)
async def health_check(request: Request) -> Response:
    """Health check endpoint for monitoring and load balancers."""
    from monarch_mcp_server.secure_session import secure_session

    has_credentials = (
        bool(os.getenv("MONARCH_TOKEN")) or
        (bool(os.getenv("MONARCH_EMAIL")) and bool(os.getenv("MONARCH_PASSWORD"))) or
        secure_session.load_token() is not None
    )
    has_github_oauth = bool(os.getenv("GITHUB_CLIENT_ID"))

    status = {
        "status": "healthy",
        "service": "monarch-mcp-server",
        "has_monarch_credentials": has_credentials,
        "github_oauth_configured": has_github_oauth,
        "base_url": get_base_url(),
    }

    return JSONResponse(status)


async def root(request: Request) -> Response:
    """Root endpoint with basic info."""
    base_url = get_base_url()
    return JSONResponse({
        "service": "Monarch Money MCP Server",
        "description": "MCP server for Monarch Money personal finance",
        "endpoints": {
            "/health": "Health check endpoint (public)",
            "/mcp": "MCP endpoint (requires GitHub OAuth)",
            "/.well-known/oauth-authorization-server": "OAuth discovery endpoint",
        },
        "auth": "GitHub OAuth - configure in Claude mobile app with OAuth client ID",
        "oauth_discovery": f"{base_url}/.well-known/oauth-authorization-server",
    })


def create_app() -> Starlette:
    """Create the Starlette ASGI application."""
    mcp_server = create_mcp_server()

    # Get the HTTP app from FastMCP (includes OAuth routes)
    mcp_app = mcp_server.http_app(path="/mcp")

    # Get well-known routes for OAuth discovery
    if mcp_server.auth:
        well_known_routes = mcp_server.auth.get_well_known_routes(mcp_path="/mcp")
    else:
        well_known_routes = []

    # Create main app combining everything
    app = Starlette(
        debug=os.getenv("DEBUG", "false").lower() == "true",
        routes=[
            Route("/", root),
            Route("/health", health_check),
            # Well-known routes at root for OAuth discovery
            *well_known_routes,
            # Mount the MCP app
            Mount("/", app=mcp_app),
        ],
        lifespan=mcp_app.lifespan,
    )

    logger.info("Monarch Money MCP HTTP Server with GitHub OAuth initialized")

    return app


# Create the ASGI app instance
app = create_app()


def main():
    """Run the HTTP server using uvicorn."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    # Validate configuration
    if not os.getenv("GITHUB_CLIENT_ID") or not os.getenv("GITHUB_CLIENT_SECRET"):
        logger.error("=" * 60)
        logger.error("ERROR: GitHub OAuth credentials required!")
        logger.error("Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET")
        logger.error("=" * 60)
        raise SystemExit(1)

    if not os.getenv("MONARCH_TOKEN"):
        logger.warning("=" * 60)
        logger.warning("WARNING: MONARCH_TOKEN not set")
        logger.warning("Run 'python login_setup.py' locally, then copy the token")
        logger.warning("=" * 60)

    base_url = get_base_url()
    logger.info(f"Starting Monarch Money MCP Server on {base_url}")
    logger.info(f"MCP endpoint: {base_url}/mcp")
    logger.info(f"OAuth discovery: {base_url}/.well-known/oauth-authorization-server")
    logger.info(f"Health check: {base_url}/health")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
