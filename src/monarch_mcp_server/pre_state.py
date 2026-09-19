"""Snapshot records before a write destroys what they held.

A delete or an update is only reversible from data captured *before* it ran —
the operation is what removes the original values. Without this, the audit log
can say what changed but never what it changed *from*, which is why rollback
records used to point the operator at data the operation had already destroyed.

Snapshots are keyed by **tool parameter name**, not by the Monarch API's field
names, so ``rollback.py`` can drop them straight into a reverse call without
a second translation step. ``merchant`` becomes both ``merchant_name`` (what
``create_transaction`` takes) and ``description`` (what ``update_transaction``
takes), because the same value restores through either path.

Capture is best-effort. If the read fails, the operation still runs and the
audit entry records the failure — refusing a delete because a snapshot read
timed out would be a worse trade than proceeding without an undo, and the
rollback plan reports itself unreversible either way.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from monarch_mcp_server.client import get_monarch_client

logger = logging.getLogger(__name__)

CaptureFn = Callable[[dict], Awaitable[dict | None]]


def _first(*values: Any) -> Any:
    """First value that is not None."""
    for value in values:
        if value is not None:
            return value
    return None


async def _capture_transaction(params: dict) -> dict | None:
    """Snapshot a transaction's restorable fields."""
    transaction_id = params.get("transaction_id")
    if not transaction_id:
        return None

    client = await get_monarch_client()
    payload = await client.get_transaction_details(transaction_id)
    txn = (payload or {}).get("getTransaction") or {}
    if not txn:
        return None

    merchant_name = (txn.get("merchant") or {}).get("name")
    return {
        "transaction_id": txn.get("id"),
        "account_id": (txn.get("account") or {}).get("id"),
        "category_id": (txn.get("category") or {}).get("id"),
        "goal_id": (txn.get("goal") or {}).get("id"),
        "amount": txn.get("amount"),
        "date": txn.get("date"),
        "notes": txn.get("notes"),
        # create_transaction calls it merchant_name; update_transaction calls
        # the same field description. Store both so either reverse call works.
        "merchant_name": merchant_name,
        "description": merchant_name,
        "hide_from_reports": txn.get("hideFromReports"),
        "needs_review": txn.get("needsReview"),
        "tag_ids": [tag["id"] for tag in txn.get("tags") or [] if tag.get("id")],
    }


async def _capture_splits(params: dict) -> dict | None:
    """Snapshot a transaction's splits in the shape the update tool accepts."""
    transaction_id = params.get("transaction_id")
    if not transaction_id:
        return None

    client = await get_monarch_client()
    payload = await client.get_transaction_splits(transaction_id)
    txn = (payload or {}).get("getTransaction") or {}

    # An empty list is meaningful: it restores "this transaction had no
    # splits", which update_transaction_splits implements by deleting them.
    splits = [
        {
            "merchantName": (split.get("merchant") or {}).get("name"),
            "amount": split.get("amount"),
            "categoryId": (split.get("category") or {}).get("id"),
        }
        for split in txn.get("splitTransactions") or []
    ]
    return {"transaction_id": transaction_id, "splits": splits}


async def _find_account(account_id: str) -> dict | None:
    client = await get_monarch_client()
    payload = await client.get_accounts()
    for account in (payload or {}).get("accounts") or []:
        if str(account.get("id")) == str(account_id):
            return account
    return None


async def _capture_account(params: dict) -> dict | None:
    """Snapshot an account's restorable fields."""
    account_id = params.get("account_id")
    if not account_id:
        return None

    account = await _find_account(str(account_id))
    if not account:
        return None

    return {
        "account_id": account.get("id"),
        # update_account takes `name`; create_manual_account takes
        # `account_name`, which rollback.py maps from this.
        "name": _first(account.get("displayName"), account.get("name")),
        "balance": account.get("currentBalance"),
        "account_type": (account.get("type") or {}).get("name"),
        "account_sub_type": (account.get("subtype") or {}).get("name"),
        "include_in_net_worth": account.get("includeInNetWorth"),
        "hide_from_summary_list": account.get("hideFromList"),
        "hide_transactions_from_reports": account.get("hideTransactionsFromReports"),
    }


def _normalize_category(category: dict) -> dict:
    return {
        "category_id": category.get("id"),
        "name": category.get("name"),
        "icon": category.get("icon"),
        "group_id": (category.get("group") or {}).get("id"),
    }


async def _all_categories() -> list[dict]:
    client = await get_monarch_client()
    payload = await client.get_transaction_categories()
    return (payload or {}).get("categories") or []


async def _capture_category(params: dict) -> dict | None:
    """Snapshot a single category."""
    category_id = params.get("category_id")
    if not category_id:
        return None

    for category in await _all_categories():
        if str(category.get("id")) == str(category_id):
            return _normalize_category(category)
    return None


async def _capture_categories(params: dict) -> dict | None:
    """Snapshot every category a bulk delete is about to remove."""
    raw = params.get("category_ids") or ""
    wanted = {part.strip() for part in str(raw).split(",") if part.strip()}
    if not wanted:
        return None

    snapshots = [
        _normalize_category(category)
        for category in await _all_categories()
        if str(category.get("id")) in wanted
    ]
    return {"categories": snapshots} if snapshots else None


async def _capture_budget(params: dict) -> dict | None:
    """Snapshot the budget amount a set is about to overwrite.

    Budgets are per-category-per-month, so an unambiguous match needs both.
    When the target period can't be pinned down, this returns None rather than
    guessing: restoring the wrong month's amount would be worse than reporting
    no snapshot.
    """
    target_id = params.get("category_id") or params.get("category_group_id")
    if not target_id:
        return None

    start_date = params.get("start_date")
    if not start_date:
        # set_budget_amount defaults to the current month; resolve it the same
        # way so the snapshot and the write target the same period.
        from datetime import datetime

        start_date = datetime.now().strftime("%Y-%m-01")

    client = await get_monarch_client()
    payload = await client.get_budgets(start_date=start_date, end_date=start_date)
    budget_data = (payload or {}).get("budgetData") or {}

    if params.get("category_id"):
        buckets = budget_data.get("monthlyAmountsByCategory") or []
        key = "category"
    else:
        buckets = budget_data.get("monthlyAmountsByCategoryGroup") or []
        key = "categoryGroup"

    month = str(start_date)[:7]
    for bucket in buckets:
        if str((bucket.get(key) or {}).get("id")) != str(target_id):
            continue
        for entry in bucket.get("monthlyAmounts") or []:
            if str(entry.get("month", ""))[:7] == month:
                return {
                    "amount": entry.get("plannedCashFlowAmount"),
                    "month": entry.get("month"),
                }
    return None


# Which snapshot each guarded operation needs. Operations absent from this map
# either need no snapshot (creates carry their own undo) or have no inverse.
_CAPTURERS: dict[str, CaptureFn] = {
    "delete_transaction": _capture_transaction,
    "update_transaction": _capture_transaction,
    "categorize_transaction": _capture_transaction,
    "add_transaction_tag": _capture_transaction,
    "set_transaction_tags": _capture_transaction,
    "update_transaction_splits": _capture_splits,
    "delete_account": _capture_account,
    "update_account": _capture_account,
    "delete_transaction_category": _capture_category,
    "delete_transaction_categories": _capture_categories,
    "set_budget_amount": _capture_budget,
}


def needs_snapshot(operation_name: str) -> bool:
    """Whether this operation destroys state that must be captured first."""
    return operation_name in _CAPTURERS


async def capture(operation_name: str, params: dict) -> tuple[dict | None, str | None]:
    """Snapshot what an operation is about to overwrite.

    Returns:
        ``(snapshot, error)``. Both are None when the operation needs no
        snapshot. ``error`` is set when capture was attempted and failed, which
        the audit entry records so the missing undo is visible rather than
        silent.
    """
    capturer = _CAPTURERS.get(operation_name)
    if capturer is None:
        return None, None

    try:
        snapshot = await capturer(params)
    except Exception as exc:  # noqa: BLE001 - never block the write on this
        message = f"{type(exc).__name__}: {exc}"
        logger.warning(
            "Pre-operation snapshot failed for %s: %s. The operation will "
            "proceed, but it will not be reversible from the audit log.",
            operation_name,
            message,
        )
        return None, message

    if snapshot is None:
        return None, "the record was not found, so nothing could be captured"

    return snapshot, None
