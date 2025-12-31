"""Monarch Money MCP Server - Main server implementation."""

import os
import logging
import atexit
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date
import json

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from monarchmoney import MonarchMoney, RequireMFAException
from pydantic import BaseModel, Field

from monarch_mcp_server.secure_session import secure_session
from monarch_mcp_server.safety import get_safety_guard, require_safety_check
from monarch_mcp_server.utils import (
    run_async,
    shutdown_executor,
    format_result,
    format_error,
    validate_date_format,
    validate_non_empty_string,
)
from monarch_mcp_server.exceptions import (
    MonarchMCPError,
    AuthenticationError,
    SessionExpiredError,
    NetworkError,
    APIError,
    ValidationError,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("Monarch Money MCP Server")

# Register cleanup on exit
atexit.register(shutdown_executor)


class MonarchConfig(BaseModel):
    """Configuration for Monarch Money connection."""

    email: Optional[str] = Field(default=None, description="Monarch Money email")
    password: Optional[str] = Field(default=None, description="Monarch Money password")
    session_file: str = Field(
        default="monarch_session.json", description="Session file path"
    )


async def get_monarch_client() -> MonarchMoney:
    """Get or create MonarchMoney client instance using secure session storage."""
    # Try to get authenticated client from secure session
    client = secure_session.get_authenticated_client()

    if client is not None:
        logger.info("✅ Using authenticated client from secure keyring storage")
        return client

    # If no secure session, try environment credentials
    email = os.getenv("MONARCH_EMAIL")
    password = os.getenv("MONARCH_PASSWORD")

    if email and password:
        try:
            client = MonarchMoney()
            await client.login(email, password)
            logger.info(
                "Successfully logged into Monarch Money with environment credentials"
            )

            # Save the session securely
            secure_session.save_authenticated_session(client)

            return client
        except Exception as e:
            logger.error(f"Failed to login to Monarch Money: {e}")
            raise

    raise RuntimeError("🔐 Authentication needed! Run: python login_setup.py")


@mcp.tool()
def setup_authentication() -> str:
    """Get instructions for setting up secure authentication with Monarch Money."""
    return """🔐 Monarch Money - One-Time Setup

1️⃣ Open Terminal and run:
   python login_setup.py

2️⃣ Enter your Monarch Money credentials when prompted
   • Email and password
   • 2FA code if you have MFA enabled

3️⃣ Session will be saved automatically and last for weeks

4️⃣ Start using Monarch tools in Claude Desktop:
   • get_accounts - View all accounts
   • get_transactions - Recent transactions
   • get_budgets - Budget information

✅ Session persists across Claude restarts
✅ No need to re-authenticate frequently
✅ All credentials stay secure in terminal"""


@mcp.tool()
def check_auth_status() -> str:
    """Check if already authenticated with Monarch Money."""
    try:
        # Check if we have a token in the keyring
        token = secure_session.load_token()
        if token:
            status = "✅ Authentication token found in secure keyring storage\n"
        else:
            status = "❌ No authentication token found in keyring\n"

        email = os.getenv("MONARCH_EMAIL")
        if email:
            status += f"📧 Environment email: {email}\n"

        status += (
            "\n💡 Try get_accounts to test connection or run login_setup.py if needed."
        )

        return status
    except Exception as e:
        return f"Error checking auth status: {str(e)}"


@mcp.tool()
def debug_session_loading() -> str:
    """Debug keyring session loading issues."""
    try:
        # Check keyring access
        token = secure_session.load_token()
        if token:
            return f"✅ Token found in keyring (length: {len(token)})"
        else:
            return "❌ No token found in keyring. Run login_setup.py to authenticate."
    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        return f"❌ Keyring access failed:\nError: {str(e)}\nType: {type(e)}\nTraceback:\n{error_details}"


@mcp.tool()
def get_accounts() -> str:
    """Get all financial accounts from Monarch Money."""
    try:

        async def _get_accounts():
            client = await get_monarch_client()
            return await client.get_accounts()

        accounts = run_async(_get_accounts())

        # Format accounts for display
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

        return json.dumps(account_list, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get accounts: {e}")
        return f"Error getting accounts: {str(e)}"


@mcp.tool()
def get_transactions(
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    account_id: Optional[str] = None,
) -> str:
    """
    Get transactions from Monarch Money.

    Args:
        limit: Number of transactions to retrieve (default: 100)
        offset: Number of transactions to skip (default: 0)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        account_id: Specific account ID to filter by
    """
    try:
        # Validate date formats if provided
        validated_start = validate_date_format(start_date, "start_date")
        validated_end = validate_date_format(end_date, "end_date")

        async def _get_transactions():
            client = await get_monarch_client()

            # Build filters
            filters = {}
            if validated_start:
                filters["start_date"] = validated_start
            if validated_end:
                filters["end_date"] = validated_end
            if account_id:
                filters["account_id"] = account_id

            return await client.get_transactions(limit=limit, offset=offset, **filters)

        transactions = run_async(_get_transactions())

        # Format transactions for display
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
                "account": txn.get("account", {}).get("displayName"),
                "merchant": txn.get("merchant", {}).get("name")
                if txn.get("merchant")
                else None,
                "is_pending": txn.get("isPending", False),
            }
            transaction_list.append(transaction_info)

        return json.dumps(transaction_list, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get transactions: {e}")
        return f"Error getting transactions: {str(e)}"


@mcp.tool()
def get_budgets() -> str:
    """Get budget information from Monarch Money."""
    try:

        async def _get_budgets():
            client = await get_monarch_client()
            return await client.get_budgets()

        budgets = run_async(_get_budgets())

        # Format budgets for display
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
        logger.error(f"Failed to get budgets: {e}")
        return f"Error getting budgets: {str(e)}"


@mcp.tool()
def get_cashflow(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> str:
    """
    Get cashflow analysis from Monarch Money.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
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
        logger.error(f"Failed to get cashflow: {e}")
        return f"Error getting cashflow: {str(e)}"


@mcp.tool()
def get_account_holdings(account_id: str) -> str:
    """
    Get investment holdings for a specific account.

    Args:
        account_id: The ID of the investment account
    """
    try:

        async def _get_holdings():
            client = await get_monarch_client()
            return await client.get_account_holdings(account_id)

        holdings = run_async(_get_holdings())

        return json.dumps(holdings, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get account holdings: {e}")
        return f"Error getting account holdings: {str(e)}"


@mcp.tool()
@require_safety_check("create_transaction")
def create_transaction(
    account_id: str,
    amount: float,
    description: str,
    date: str,
    category_id: Optional[str] = None,
    merchant_name: Optional[str] = None,
) -> str:
    """
    Create a new transaction in Monarch Money.

    Args:
        account_id: The account ID to add the transaction to
        amount: Transaction amount (positive for income, negative for expenses)
        description: Transaction description
        date: Transaction date in YYYY-MM-DD format
        category_id: Optional category ID
        merchant_name: Optional merchant name

    Safety: Rate limited to 10/min, 100/day
    """
    try:
        # Validate required inputs
        validate_non_empty_string(account_id, "account_id")
        validate_non_empty_string(description, "description")
        validated_date = validate_date_format(date, "date")

        async def _create_transaction():
            client = await get_monarch_client()

            transaction_data = {
                "account_id": account_id,
                "amount": amount,
                "description": description,
                "date": validated_date,
            }

            if category_id:
                transaction_data["category_id"] = category_id
            if merchant_name:
                transaction_data["merchant_name"] = merchant_name

            return await client.create_transaction(**transaction_data)

        result = run_async(_create_transaction())

        return json.dumps(result, indent=2, default=str)
    except ValidationError as e:
        return f"Validation error: {str(e)}"
    except Exception as e:
        logger.error(f"Failed to create transaction: {e}")
        return f"Error creating transaction: {str(e)}"


@mcp.tool()
@require_safety_check("update_transaction")
def update_transaction(
    transaction_id: str,
    amount: Optional[float] = None,
    description: Optional[str] = None,
    category_id: Optional[str] = None,
    date: Optional[str] = None,
) -> str:
    """
    Update an existing transaction in Monarch Money.

    Safety: Rate limited to 20/min

    Args:
        transaction_id: The ID of the transaction to update
        amount: New transaction amount
        description: New transaction description
        category_id: New category ID
        date: New transaction date in YYYY-MM-DD format
    """
    try:
        # Validate required inputs
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
        return f"Validation error: {str(e)}"
    except Exception as e:
        logger.error(f"Failed to update transaction: {e}")
        return f"Error updating transaction: {str(e)}"


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
        logger.error(f"Failed to refresh accounts: {e}")
        return f"Error refreshing accounts: {str(e)}"


# ============================================================================
# Additional Read-Only Tools
# ============================================================================


@mcp.tool()
def get_account_history(
    account_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """
    Get daily account balance history for a specific account.

    Args:
        account_id: The ID of the account
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
    """
    try:

        async def _get_history():
            client = await get_monarch_client()
            filters = {"account_id": account_id}
            if start_date:
                filters["start_date"] = start_date
            if end_date:
                filters["end_date"] = end_date
            return await client.get_account_history(**filters)

        history = run_async(_get_history())
        return json.dumps(history, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get account history: {e}")
        return f"Error getting account history: {str(e)}"


@mcp.tool()
def get_account_type_options() -> str:
    """Get all available account types and subtypes in Monarch Money."""
    try:

        async def _get_types():
            client = await get_monarch_client()
            return await client.get_account_type_options()

        types_data = run_async(_get_types())
        return json.dumps(types_data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get account type options: {e}")
        return f"Error getting account type options: {str(e)}"


@mcp.tool()
def get_institutions() -> str:
    """Get all linked financial institutions."""
    try:

        async def _get_institutions():
            client = await get_monarch_client()
            return await client.get_institutions()

        institutions = run_async(_get_institutions())
        return json.dumps(institutions, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get institutions: {e}")
        return f"Error getting institutions: {str(e)}"


@mcp.tool()
def get_transaction_categories() -> str:
    """Get all transaction categories."""
    try:

        async def _get_categories():
            client = await get_monarch_client()
            return await client.get_transaction_categories()

        categories = run_async(_get_categories())
        return json.dumps(categories, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get transaction categories: {e}")
        return f"Error getting transaction categories: {str(e)}"


@mcp.tool()
def get_transaction_category_groups() -> str:
    """Get all transaction category groups."""
    try:

        async def _get_groups():
            client = await get_monarch_client()
            return await client.get_transaction_category_groups()

        groups = run_async(_get_groups())
        return json.dumps(groups, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get transaction category groups: {e}")
        return f"Error getting transaction category groups: {str(e)}"


@mcp.tool()
def get_transaction_tags() -> str:
    """Get all transaction tags."""
    try:

        async def _get_tags():
            client = await get_monarch_client()
            return await client.get_transaction_tags()

        tags = run_async(_get_tags())
        return json.dumps(tags, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get transaction tags: {e}")
        return f"Error getting transaction tags: {str(e)}"


@mcp.tool()
def get_transaction_details(transaction_id: str) -> str:
    """
    Get detailed information about a specific transaction.

    Args:
        transaction_id: The ID of the transaction
    """
    try:

        async def _get_details():
            client = await get_monarch_client()
            return await client.get_transaction_details(transaction_id)

        details = run_async(_get_details())
        return json.dumps(details, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get transaction details: {e}")
        return f"Error getting transaction details: {str(e)}"


@mcp.tool()
def get_transaction_splits(transaction_id: str) -> str:
    """
    Get split information for a specific transaction.

    Args:
        transaction_id: The ID of the transaction
    """
    try:

        async def _get_splits():
            client = await get_monarch_client()
            return await client.get_transaction_splits(transaction_id)

        splits = run_async(_get_splits())
        return json.dumps(splits, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get transaction splits: {e}")
        return f"Error getting transaction splits: {str(e)}"


@mcp.tool()
def get_recurring_transactions() -> str:
    """Get all recurring transactions with merchant and account details."""
    try:

        async def _get_recurring():
            client = await get_monarch_client()
            return await client.get_recurring_transactions()

        recurring = run_async(_get_recurring())
        return json.dumps(recurring, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get recurring transactions: {e}")
        return f"Error getting recurring transactions: {str(e)}"


@mcp.tool()
def get_transactions_summary(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> str:
    """
    Get aggregated transaction summary data.

    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
    """
    try:

        async def _get_summary():
            client = await get_monarch_client()
            filters = {}
            if start_date:
                filters["start_date"] = start_date
            if end_date:
                filters["end_date"] = end_date
            return await client.get_transactions_summary(**filters)

        summary = run_async(_get_summary())
        return json.dumps(summary, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get transactions summary: {e}")
        return f"Error getting transactions summary: {str(e)}"


@mcp.tool()
def get_cashflow_summary(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> str:
    """
    Get aggregated cashflow summary data.

    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
    """
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
        logger.error(f"Failed to get cashflow summary: {e}")
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
        logger.error(f"Failed to get subscription details: {e}")
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
        logger.error(f"Failed to check refresh status: {e}")
        return f"Error checking refresh status: {str(e)}"


# ============================================================================
# Write Operation Tools
# ============================================================================


@mcp.tool()
@require_safety_check("delete_transaction")
def delete_transaction(transaction_id: str, confirmed: bool = False) -> str:
    """
    Delete a transaction from Monarch Money.

    Args:
        transaction_id: The ID of the transaction to delete

    Safety: Rate limited to 5/min, 50/day
    """
    try:

        async def _delete_transaction():
            client = await get_monarch_client()
            return await client.delete_transaction(transaction_id)

        result = run_async(_delete_transaction())
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to delete transaction: {e}")
        return f"Error deleting transaction: {str(e)}"


@mcp.tool()
@require_safety_check("create_transaction_category")
def create_transaction_category(name: str, group_id: Optional[str] = None) -> str:
    """
    Create a new transaction category.

    Args:
        name: Name of the new category
        group_id: Optional category group ID to assign the category to

    Safety: Rate limited to 5/min
    """
    try:

        async def _create_category():
            client = await get_monarch_client()
            if group_id:
                return await client.create_transaction_category(
                    name=name, group_id=group_id
                )
            return await client.create_transaction_category(name=name)

        result = run_async(_create_category())
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to create transaction category: {e}")
        return f"Error creating transaction category: {str(e)}"


@mcp.tool()
@require_safety_check("delete_transaction_category")
def delete_transaction_category(category_id: str, confirmed: bool = False) -> str:
    """
    Delete a transaction category.

    Args:
        category_id: The ID of the category to delete
    """
    try:

        async def _delete_category():
            client = await get_monarch_client()
            return await client.delete_transaction_category(category_id)

        result = run_async(_delete_category())
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to delete transaction category: {e}")
        return f"Error deleting transaction category: {str(e)}"


@mcp.tool()
@require_safety_check("delete_transaction_categories")
def delete_transaction_categories(category_ids: str, confirmed: bool = False) -> str:
    """
    Delete multiple transaction categories.

    Args:
        category_ids: Comma-separated list of category IDs to delete
    """
    try:

        async def _delete_categories():
            client = await get_monarch_client()
            ids_list = [id.strip() for id in category_ids.split(",")]
            return await client.delete_transaction_categories(ids_list)

        result = run_async(_delete_categories())
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to delete transaction categories: {e}")
        return f"Error deleting transaction categories: {str(e)}"


@mcp.tool()
@require_safety_check("create_manual_account")
def create_manual_account(
    account_name: str,
    account_type: str,
    current_balance: float,
    account_subtype: Optional[str] = None,
) -> str:
    """
    Create a manual account (not linked to a financial institution).

    Args:
        account_name: Name of the account
        account_type: Type of account (e.g., 'checking', 'savings', 'credit')
        current_balance: Current account balance
        account_subtype: Optional account subtype
    """
    try:
        # Validate required inputs
        validate_non_empty_string(account_name, "account_name")
        validate_non_empty_string(account_type, "account_type")

        async def _create_account():
            client = await get_monarch_client()
            account_data = {
                "account_name": account_name,
                "type": account_type,
                "balance": current_balance,
            }
            if account_subtype:
                account_data["subtype"] = account_subtype
            return await client.create_manual_account(**account_data)

        result = run_async(_create_account())
        return json.dumps(result, indent=2, default=str)
    except ValidationError as e:
        return f"Validation error: {str(e)}"
    except Exception as e:
        logger.error(f"Failed to create manual account: {e}")
        return f"Error creating manual account: {str(e)}"


@mcp.tool()
@require_safety_check("delete_account")
def delete_account(account_id: str, confirmed: bool = False) -> str:
    """
    Delete an account from Monarch Money.

    Args:
        account_id: The ID of the account to delete
    """
    try:

        async def _delete_account():
            client = await get_monarch_client()
            return await client.delete_account(account_id)

        result = run_async(_delete_account())
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to delete account: {e}")
        return f"Error deleting account: {str(e)}"


@mcp.tool()
@require_safety_check("update_account")
def update_account(
    account_id: str,
    name: Optional[str] = None,
    balance: Optional[float] = None,
    account_type: Optional[str] = None,
) -> str:
    """
    Update account settings or balance.

    Args:
        account_id: The ID of the account to update
        name: New account name (optional)
        balance: New account balance (optional)
        account_type: New account type (optional)
    """
    try:

        async def _update_account():
            client = await get_monarch_client()
            update_data = {"account_id": account_id}
            if name is not None:
                update_data["name"] = name
            if balance is not None:
                update_data["balance"] = balance
            if account_type is not None:
                update_data["type"] = account_type
            return await client.update_account(**update_data)

        result = run_async(_update_account())
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to update account: {e}")
        return f"Error updating account: {str(e)}"


@mcp.tool()
@require_safety_check("update_transaction_splits")
def update_transaction_splits(
    transaction_id: str, splits_data: str
) -> str:
    """
    Update or create transaction splits.

    Args:
        transaction_id: The ID of the transaction
        splits_data: JSON string containing split information
                     Example: '[{"amount": 50.00, "category_id": "123"}, {"amount": 30.00, "category_id": "456"}]'
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
        logger.error(f"Failed to update transaction splits: {e}")
        return f"Error updating transaction splits: {str(e)}"


@mcp.tool()
@require_safety_check("create_tag")
def create_tag(name: str, color: Optional[str] = None) -> str:
    """
    Create a new transaction tag.

    Args:
        name: Name of the new tag
        color: Optional color for the tag (hex format, e.g., '#FF5733')
    """
    try:
        # Validate required inputs
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
        logger.error(f"Failed to create tag: {e}")
        return f"Error creating tag: {str(e)}"


@mcp.tool()
@require_safety_check("set_transaction_tags")
def set_transaction_tags(transaction_id: str, tag_ids: str) -> str:
    """
    Assign tags to a transaction.

    Args:
        transaction_id: The ID of the transaction
        tag_ids: Comma-separated list of tag IDs to assign
    """
    try:

        async def _set_tags():
            client = await get_monarch_client()
            ids_list = [id.strip() for id in tag_ids.split(",")]
            return await client.set_transaction_tags(transaction_id, ids_list)

        result = run_async(_set_tags())
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to set transaction tags: {e}")
        return f"Error setting transaction tags: {str(e)}"


@mcp.tool()
@require_safety_check("set_budget_amount")
def set_budget_amount(category_id: str, amount: float) -> str:
    """
    Set or update budget amount for a category. Set to 0 to clear the budget.

    Args:
        category_id: The ID of the category
        amount: Budget amount (set to 0 to clear budget)
    """
    try:

        async def _set_budget():
            client = await get_monarch_client()
            return await client.set_budget_amount(category_id, amount)

        result = run_async(_set_budget())
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to set budget amount: {e}")
        return f"Error setting budget amount: {str(e)}"


@mcp.tool()
@require_safety_check("upload_account_balance_history")
def upload_account_balance_history(
    account_id: str, csv_data: str, confirmed: bool = False
) -> str:
    """
    Upload account balance history from CSV data.

    Args:
        account_id: The ID of the account
        csv_data: CSV data with date and balance columns
                  Example format:
                  date,balance
                  2024-01-01,1000.00
                  2024-01-02,1050.00
    """
    try:

        async def _upload_history():
            client = await get_monarch_client()
            return await client.upload_account_balance_history(account_id, csv_data)

        result = run_async(_upload_history())
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to upload account balance history: {e}")
        return f"Error uploading account balance history: {str(e)}"


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
        logger.error(f"Failed to refresh and wait: {e}")
        return f"Error refreshing and waiting: {str(e)}"


# ============================================================================
# Safety Management Tools
# ============================================================================


@mcp.tool()
def get_safety_stats() -> str:
    """
    Get current safety statistics including rate limits and daily operation counts.

    Shows:
    - Operations performed today
    - Current rate usage (last minute)
    - Configured limits
    - Emergency stop status
    """
    try:
        guard = get_safety_guard()
        stats = guard.get_operation_stats()
        return json.dumps(stats, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get safety stats: {e}")
        return f"Error getting safety stats: {str(e)}"


@mcp.tool()
def enable_emergency_stop() -> str:
    """
    EMERGENCY: Disable all write operations immediately.

    Use this if you detect runaway behavior or want to prevent any modifications.
    This will block all create, update, and delete operations until manually disabled.

    To re-enable: Use disable_emergency_stop() or edit ~/.mm/safety_config.json
    """
    try:
        guard = get_safety_guard()
        return guard.enable_emergency_stop()
    except Exception as e:
        logger.error(f"Failed to enable emergency stop: {e}")
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
        logger.error(f"Failed to disable emergency stop: {e}")
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
        logger.error(f"Failed to get recent operations: {e}")
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
        logger.error(f"Failed to get rollback suggestions: {e}")
        return f"Error getting rollback suggestions: {str(e)}"


def main():
    """Main entry point for the server."""
    logger.info("Starting Monarch Money MCP Server...")
    try:
        mcp.run()
    except Exception as e:
        logger.error(f"Failed to run server: {str(e)}")
        raise


# Export for mcp run
app = mcp

if __name__ == "__main__":
    main()
