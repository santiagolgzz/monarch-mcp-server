"""Response shapes the Monarch SDK actually returns.

Every mutation in ``monarchmoney`` returns a GraphQL envelope: the mutation
name at the top level, the entity nested under it, and an ``errors`` sibling.
The old tests mocked flat dicts like ``{"id": "txn_1"}`` — a shape the API
never produces — so ``_extract_id_from_result`` passed its tests while
returning None against every real response, and rollback silently recorded
``created_id: None`` next to ``reversible: True``.

These fixtures are transcribed from the mutation documents in
``monarchmoney/monarchmoney.py``. ``tests/test_sdk_fixture_shapes.py`` checks
them back against those documents, so a fixture cannot drift into fiction the
way the mocks it replaces did.

Use these anywhere a test needs a create/update/delete result.
"""

from __future__ import annotations

from typing import Any


def create_transaction_response(transaction_id: str = "txn_created_1") -> dict:
    """``Common_CreateTransactionMutation`` — createTransaction.transaction.id."""
    return {
        "createTransaction": {
            "errors": None,
            "transaction": {"id": transaction_id, "__typename": "Transaction"},
            "__typename": "CreateTransactionMutationPayload",
        }
    }


def create_manual_account_response(account_id: str = "acc_created_1") -> dict:
    """``Web_CreateManualAccount`` — createManualAccount.account.id."""
    return {
        "createManualAccount": {
            "account": {"id": account_id, "__typename": "Account"},
            "errors": None,
            "__typename": "CreateManualAccountMutationPayload",
        }
    }


def create_category_response(category_id: str = "cat_created_1") -> dict:
    """``Web_CreateCategory`` — createCategory.category.id."""
    return {
        "createCategory": {
            "errors": None,
            "category": {
                "id": category_id,
                "name": "New Category",
                "__typename": "Category",
            },
            "__typename": "CreateCategoryPayload",
        }
    }


def create_tag_response(tag_id: str = "tag_created_1") -> dict:
    """``Common_CreateTransactionTag`` — createTransactionTag.tag.id."""
    return {
        "createTransactionTag": {
            "tag": {
                "id": tag_id,
                "name": "New Tag",
                "color": "#ff0000",
                "order": 1,
                "transactionCount": 0,
                "__typename": "TransactionTag",
            },
            "errors": None,
            "__typename": "CreateTransactionTagPayload",
        }
    }


def delete_transaction_response(deleted: bool = True) -> dict:
    """``Common_DeleteTransactionMutation`` — carries no entity ID."""
    return {
        "deleteTransaction": {
            "deleted": deleted,
            "errors": None,
            "__typename": "DeleteTransactionMutationPayload",
        }
    }


def failed_mutation_response(
    mutation: str = "createTransaction",
    message: str = "Amount is required",
    field: str = "amount",
) -> dict:
    """A mutation that reported business-level errors and created nothing.

    Monarch returns HTTP 200 with a populated ``errors`` field rather than
    raising, so this is what a silent no-op looks like on the wire.
    """
    return {
        mutation: {
            "errors": {
                "fieldErrors": [{"field": field, "messages": [message]}],
                "message": message,
                "code": "VALIDATION_ERROR",
                "__typename": "PayloadError",
            },
            "transaction": None,
            "__typename": f"{mutation[0].upper()}{mutation[1:]}Payload",
        }
    }


# --- Entity snapshots, as the read APIs return them -----------------------


def transaction_detail(transaction_id: str = "txn_1") -> dict[str, Any]:
    """``get_transaction_details`` — the shape pre-state capture reads."""
    return {
        "getTransaction": {
            "id": transaction_id,
            "amount": -42.5,
            "date": "2026-03-04",
            "notes": "lunch",
            "hideFromReports": False,
            "needsReview": False,
            "merchant": {"id": "mer_1", "name": "Cafe Example"},
            "category": {"id": "cat_food", "name": "Restaurants"},
            "account": {"id": "acc_checking", "displayName": "Checking"},
            "tags": [
                {"id": "tag_a", "name": "work"},
                {"id": "tag_b", "name": "reimbursable"},
            ],
            "__typename": "Transaction",
        }
    }


def accounts_response(account_id: str = "acc_checking") -> dict[str, Any]:
    """``get_accounts`` — the shape account pre-state capture reads."""
    return {
        "accounts": [
            {
                "id": account_id,
                "displayName": "Checking",
                "currentBalance": 1234.56,
                "includeInNetWorth": True,
                "type": {"name": "depository", "display": "Cash"},
                "subtype": {"name": "checking", "display": "Checking"},
                "__typename": "Account",
            }
        ]
    }


def categories_response(category_id: str = "cat_food") -> dict[str, Any]:
    """``get_transaction_categories`` — the shape category capture reads."""
    return {
        "categories": [
            {
                "id": category_id,
                "name": "Restaurants",
                "icon": "🍽️",
                "group": {"id": "grp_spending", "name": "Spending"},
                "__typename": "Category",
            }
        ]
    }


def budgets_response(
    category_id: str = "cat_food",
    month: str = "2026-03-01",
    budgeted: float = 300.0,
) -> dict[str, Any]:
    """``get_budgets`` — GetJointPlanningData, nested under ``budgetData``.

    There is no top-level ``budgets`` key. The tool read one for months and so
    always returned an empty list; the conftest mock returned the invented
    shape, so nothing caught it.
    """
    return {
        "budgetData": {
            "monthlyAmountsByCategory": [
                {
                    "category": {"id": category_id, "__typename": "Category"},
                    "monthlyAmounts": [
                        {
                            "month": month,
                            "plannedCashFlowAmount": budgeted,
                            "plannedSetAsideAmount": 0.0,
                            "actualAmount": 120.0,
                            "remainingAmount": budgeted - 120.0,
                            "previousMonthRolloverAmount": 0.0,
                            "rolloverType": None,
                            "__typename": "BudgetMonthlyAmounts",
                        }
                    ],
                    "__typename": "BudgetCategoryMonthlyAmounts",
                }
            ],
            "monthlyAmountsByCategoryGroup": [],
            "__typename": "BudgetData",
        }
    }


def transaction_splits_response(transaction_id: str = "txn_1") -> dict[str, Any]:
    """``get_transaction_splits`` — splits hang off ``getTransaction``."""
    return {
        "getTransaction": {
            "id": transaction_id,
            "amount": -100.0,
            "category": {"id": "cat_food", "name": "Restaurants"},
            "merchant": {"id": "mer_1", "name": "Cafe Example"},
            "splitTransactions": [
                {
                    "id": "split_1",
                    "merchant": {"id": "mer_1", "name": "Cafe Example"},
                    "category": {"id": "cat_food", "name": "Restaurants"},
                    "amount": -60.0,
                    "notes": "food",
                },
                {
                    "id": "split_2",
                    "merchant": {"id": "mer_1", "name": "Cafe Example"},
                    "category": {"id": "cat_tip", "name": "Tips"},
                    "amount": -40.0,
                    "notes": None,
                },
            ],
            "__typename": "Transaction",
        }
    }
