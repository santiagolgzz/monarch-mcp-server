"""Tests for pre-operation snapshots.

Snapshots are what make a delete or an update reversible, so two properties
matter: the keys must be the ones ``rollback.py`` feeds into a reverse call,
and a capture failure must never take the write down with it.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from monarch_mcp_server import pre_state
from monarch_mcp_server.rollback import build_rollback

from . import sdk_fixtures


@pytest.fixture
def client():
    """Patch the Monarch client the capturers reach for."""
    mock = AsyncMock()
    mock.get_transaction_details.return_value = sdk_fixtures.transaction_detail()
    mock.get_transaction_splits.return_value = (
        sdk_fixtures.transaction_splits_response()
    )
    mock.get_accounts.return_value = sdk_fixtures.accounts_response()
    mock.get_transaction_categories.return_value = sdk_fixtures.categories_response()
    mock.get_budgets.return_value = sdk_fixtures.budgets_response()
    with patch.object(pre_state, "get_monarch_client", return_value=mock):
        yield mock


class TestNeedsSnapshot:
    @pytest.mark.parametrize(
        "operation",
        [
            "delete_transaction",
            "update_transaction",
            "delete_account",
            "update_account",
            "delete_transaction_category",
            "delete_transaction_categories",
            "categorize_transaction",
            "add_transaction_tag",
            "set_transaction_tags",
            "set_budget_amount",
            "update_transaction_splits",
        ],
    )
    def test_destructive_and_update_operations_need_one(self, operation):
        assert pre_state.needs_snapshot(operation)

    @pytest.mark.parametrize(
        "operation",
        ["create_transaction", "create_manual_account", "create_tag"],
    )
    def test_creates_do_not(self, operation):
        """A create carries its own undo — the new ID is in the result."""
        assert not pre_state.needs_snapshot(operation)


class TestTransactionSnapshot:
    async def test_captures_the_fields_a_recreate_needs(self, client):
        snapshot, error = await pre_state.capture(
            "delete_transaction", {"transaction_id": "txn_1"}
        )
        assert error is None
        assert snapshot["account_id"] == "acc_checking"
        assert snapshot["amount"] == -42.5
        assert snapshot["merchant_name"] == "Cafe Example"
        assert snapshot["category_id"] == "cat_food"
        assert snapshot["date"] == "2026-03-04"
        assert snapshot["notes"] == "lunch"

    async def test_stores_merchant_under_both_parameter_names(self, client):
        """create_transaction says merchant_name, update_transaction says
        description. The same value restores through either."""
        snapshot, _ = await pre_state.capture(
            "update_transaction", {"transaction_id": "txn_1"}
        )
        assert snapshot["merchant_name"] == snapshot["description"] == "Cafe Example"

    async def test_captures_tag_ids_for_tag_restores(self, client):
        snapshot, _ = await pre_state.capture(
            "add_transaction_tag", {"transaction_id": "txn_1", "tag_id": "tag_new"}
        )
        assert snapshot["tag_ids"] == ["tag_a", "tag_b"]

    async def test_snapshot_feeds_a_working_recreate_call(self, client):
        """The end-to-end property: snapshot in, executable reverse call out."""
        snapshot, _ = await pre_state.capture(
            "delete_transaction", {"transaction_id": "txn_1"}
        )
        plan = build_rollback(
            "delete_transaction",
            {"transaction_id": "txn_1"},
            sdk_fixtures.delete_transaction_response(),
            snapshot,
        )
        assert plan["reversible"] is True
        assert plan["reverse_call"]["tool"] == "create_transaction"
        # Every argument create_transaction requires must be present.
        for required in (
            "account_id",
            "amount",
            "merchant_name",
            "category_id",
            "date",
        ):
            assert plan["reverse_call"]["arguments"][required] is not None


class TestSplitsSnapshot:
    async def test_normalizes_to_the_update_tools_input_shape(self, client):
        snapshot, error = await pre_state.capture(
            "update_transaction_splits",
            {"transaction_id": "txn_1", "splits_data": "[]"},
        )
        assert error is None
        assert snapshot["splits"] == [
            {
                "merchantName": "Cafe Example",
                "amount": -60.0,
                "categoryId": "cat_food",
            },
            {"merchantName": "Cafe Example", "amount": -40.0, "categoryId": "cat_tip"},
        ]

    async def test_an_unsplit_transaction_captures_an_empty_list(self, client):
        """Restoring "had no splits" means passing [], which deletes them."""
        client.get_transaction_splits.return_value = {
            "getTransaction": {"id": "txn_1", "splitTransactions": []}
        }
        snapshot, _ = await pre_state.capture(
            "update_transaction_splits", {"transaction_id": "txn_1"}
        )
        assert snapshot["splits"] == []
        plan = build_rollback(
            "update_transaction_splits", {"transaction_id": "txn_1"}, {}, snapshot
        )
        assert plan["reversible"] is True
        assert plan["reverse_call"]["arguments"]["splits_data"] == "[]"


class TestAccountSnapshot:
    async def test_captures_fields_for_recreate_and_update(self, client):
        snapshot, error = await pre_state.capture(
            "delete_account", {"account_id": "acc_checking"}
        )
        assert error is None
        assert snapshot["name"] == "Checking"
        assert snapshot["account_type"] == "depository"
        assert snapshot["account_sub_type"] == "checking"
        assert snapshot["balance"] == 1234.56

    async def test_unknown_account_reports_nothing_captured(self, client):
        snapshot, error = await pre_state.capture(
            "delete_account", {"account_id": "acc_missing"}
        )
        assert snapshot is None
        assert "not found" in error


class TestCategorySnapshot:
    async def test_captures_name_and_group(self, client):
        snapshot, _ = await pre_state.capture(
            "delete_transaction_category", {"category_id": "cat_food"}
        )
        assert snapshot["name"] == "Restaurants"
        assert snapshot["group_id"] == "grp_spending"

    async def test_bulk_delete_captures_each_matching_category(self, client):
        client.get_transaction_categories.return_value = {
            "categories": [
                {"id": "c1", "name": "A", "group": {"id": "g1"}},
                {"id": "c2", "name": "B", "group": {"id": "g1"}},
                {"id": "c3", "name": "C", "group": {"id": "g1"}},
            ]
        }
        snapshot, _ = await pre_state.capture(
            "delete_transaction_categories", {"category_ids": "c1, c3"}
        )
        assert [c["name"] for c in snapshot["categories"]] == ["A", "C"]


class TestBudgetSnapshot:
    async def test_captures_the_planned_amount_for_the_target_month(self, client):
        snapshot, error = await pre_state.capture(
            "set_budget_amount",
            {"category_id": "cat_food", "start_date": "2026-03-01", "amount": 500},
        )
        assert error is None
        assert snapshot["amount"] == 300.0

    async def test_returns_nothing_when_the_month_does_not_match(self, client):
        """Restoring the wrong month's amount is worse than no snapshot."""
        snapshot, error = await pre_state.capture(
            "set_budget_amount",
            {"category_id": "cat_food", "start_date": "2026-09-01", "amount": 500},
        )
        assert snapshot is None
        assert error

    async def test_returns_nothing_for_an_unknown_category(self, client):
        snapshot, _ = await pre_state.capture(
            "set_budget_amount",
            {"category_id": "cat_other", "start_date": "2026-03-01", "amount": 5},
        )
        assert snapshot is None


class TestCaptureIsBestEffort:
    async def test_a_failing_read_returns_an_error_not_an_exception(self, client):
        """A snapshot read that blows up must never take the write with it."""
        client.get_transaction_details.side_effect = RuntimeError("upstream 500")
        snapshot, error = await pre_state.capture(
            "delete_transaction", {"transaction_id": "txn_1"}
        )
        assert snapshot is None
        assert "RuntimeError: upstream 500" in error

    async def test_unregistered_operations_capture_nothing_quietly(self, client):
        snapshot, error = await pre_state.capture("create_transaction", {})
        assert snapshot is None and error is None

    async def test_missing_identifier_is_not_an_exception(self, client):
        snapshot, error = await pre_state.capture("delete_transaction", {})
        assert snapshot is None
        assert error
