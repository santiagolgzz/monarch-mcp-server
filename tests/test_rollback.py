"""Tests for rollback planning.

The rule under test throughout: ``reversible`` is true only when
``reverse_call`` is a complete, executable call. A plan that says an operation
can be undone while carrying no ID, no prior values, or no snapshot is the
failure mode this module was written to end.
"""

from __future__ import annotations

import pytest

from monarch_mcp_server.rollback import (
    build_rollback,
    extract_entity_id,
    payload_errors,
)

from . import sdk_fixtures


class TestExtractEntityId:
    """ID extraction against the shapes the SDK really returns."""

    def test_finds_id_in_real_create_transaction_envelope(self):
        result = sdk_fixtures.create_transaction_response("txn_abc")
        assert extract_entity_id(result) == "txn_abc"

    def test_finds_id_in_real_create_account_envelope(self):
        result = sdk_fixtures.create_manual_account_response("acc_xyz")
        assert extract_entity_id(result) == "acc_xyz"

    def test_finds_id_in_real_create_category_envelope(self):
        result = sdk_fixtures.create_category_response("cat_9")
        assert extract_entity_id(result) == "cat_9"

    def test_finds_id_in_real_create_tag_envelope(self):
        result = sdk_fixtures.create_tag_response("tag_7")
        assert extract_entity_id(result) == "tag_7"

    def test_still_handles_a_flat_dict(self):
        """Some SDK helpers return an unwrapped entity; both must work."""
        assert extract_entity_id({"id": "flat_1"}) == "flat_1"

    def test_parses_a_json_string_result(self):
        assert (
            extract_entity_id('{"createTransaction":{"transaction":{"id":"s1"}}}')
            == "s1"
        )

    def test_prefers_the_shallowest_id(self):
        """The entity's own ID, not one belonging to something nested in it."""
        result = {"id": "txn_outer", "category": {"id": "cat_inner"}}
        assert extract_entity_id(result) == "txn_outer"

    def test_ignores_ids_inside_the_errors_subtree(self):
        result = {
            "createTransaction": {"errors": [{"id": "err_1"}], "transaction": None}
        }
        assert extract_entity_id(result) is None

    def test_returns_none_for_a_failed_mutation(self):
        assert extract_entity_id(sdk_fixtures.failed_mutation_response()) is None

    @pytest.mark.parametrize("value", [None, "", "not json", 42, [], {}])
    def test_returns_none_for_unusable_results(self, value):
        assert extract_entity_id(value) is None

    def test_does_not_mistake_a_nested_object_for_an_id(self):
        assert (
            extract_entity_id({"id": {"nested": "no"}, "transaction_id": "t1"}) == "t1"
        )

    def test_terminates_on_deeply_nested_input(self):
        deep: dict = {"id": "found"}
        for _ in range(50):
            deep = {"wrap": deep}
        assert extract_entity_id(deep) is None


class TestPayloadErrors:
    def test_surfaces_business_level_errors(self):
        errors = payload_errors(sdk_fixtures.failed_mutation_response())
        assert errors and "Amount is required" in str(errors)

    def test_empty_when_the_mutation_succeeded(self):
        assert payload_errors(sdk_fixtures.create_transaction_response()) == []


class TestCreateRollback:
    """Creates are reversible from the result alone — if the ID is found."""

    def test_create_transaction_yields_an_executable_delete(self):
        plan = build_rollback(
            "create_transaction",
            {"account_id": "acc_1", "amount": -5},
            sdk_fixtures.create_transaction_response("txn_new"),
        )
        assert plan["reversible"] is True
        assert plan["created_id"] == "txn_new"
        assert plan["reverse_call"] == {
            "tool": "delete_transaction",
            "arguments": {"transaction_id": "txn_new"},
        }

    def test_create_account_yields_an_executable_delete(self):
        plan = build_rollback(
            "create_manual_account",
            {"account_name": "Cash"},
            sdk_fixtures.create_manual_account_response("acc_new"),
        )
        assert plan["reverse_call"] == {
            "tool": "delete_account",
            "arguments": {"account_id": "acc_new"},
        }

    def test_create_category_yields_an_executable_delete(self):
        plan = build_rollback(
            "create_transaction_category",
            {"name": "Coffee", "group_id": "grp_1"},
            sdk_fixtures.create_category_response("cat_new"),
        )
        assert plan["reverse_call"] == {
            "tool": "delete_transaction_category",
            "arguments": {"category_id": "cat_new"},
        }

    def test_failed_create_is_not_reversible_and_says_why(self):
        plan = build_rollback(
            "create_transaction",
            {"amount": None},
            sdk_fixtures.failed_mutation_response(),
        )
        assert plan["reversible"] is False
        assert plan["reverse_call"] is None
        assert "no entity ID" in plan["blocked_reason"]
        assert plan["payload_errors"]

    def test_create_tag_is_honest_about_having_no_undo(self):
        """No delete-tag tool exists, so claiming reversibility would lie."""
        plan = build_rollback(
            "create_tag", {"name": "x"}, sdk_fixtures.create_tag_response("tag_1")
        )
        assert plan["reversible"] is False
        assert "no tool for deleting a tag" in plan["blocked_reason"]


class TestDeleteRollbackWithoutSnapshot:
    """Without pre-state, a delete is not reversible. Saying otherwise lied."""

    @pytest.mark.parametrize(
        ("operation", "params"),
        [
            ("delete_transaction", {"transaction_id": "txn_1"}),
            ("delete_account", {"account_id": "acc_1"}),
            ("delete_transaction_category", {"category_id": "cat_1"}),
        ],
    )
    def test_delete_without_snapshot_is_not_reversible(self, operation, params):
        plan = build_rollback(operation, params, {"deleted": True}, pre_state=None)
        assert plan["reversible"] is False
        assert plan["reverse_call"] is None
        assert "No pre-operation snapshot" in plan["blocked_reason"]


class TestDeleteRollbackWithSnapshot:
    """With pre-state, the plan is a real recreate call."""

    def test_delete_transaction_recreates_from_snapshot(self):
        pre_state = {
            "account_id": "acc_1",
            "amount": -42.5,
            "merchant_name": "Cafe Example",
            "category_id": "cat_food",
            "date": "2026-03-04",
            "notes": "lunch",
        }
        plan = build_rollback(
            "delete_transaction",
            {"transaction_id": "txn_1"},
            sdk_fixtures.delete_transaction_response(),
            pre_state=pre_state,
        )
        assert plan["reversible"] is True
        assert plan["reverse_call"]["tool"] == "create_transaction"
        assert plan["reverse_call"]["arguments"] == pre_state
        assert "new ID" in plan["notes"]

    def test_incomplete_snapshot_is_not_reversible(self):
        """A snapshot missing required fields can't rebuild the record."""
        plan = build_rollback(
            "delete_transaction",
            {"transaction_id": "txn_1"},
            {},
            pre_state={"amount": -42.5},  # no account, category or date
        )
        assert plan["reversible"] is False
        assert "lacked the fields needed" in plan["blocked_reason"]

    def test_delete_account_warns_history_is_not_restored(self):
        plan = build_rollback(
            "delete_account",
            {"account_id": "acc_1"},
            {},
            pre_state={
                "name": "Checking",
                "account_type": "depository",
                "balance": 100.0,
            },
        )
        assert plan["reversible"] is True
        assert plan["reverse_call"]["tool"] == "create_manual_account"
        assert plan["reverse_call"]["arguments"]["account_name"] == "Checking"
        assert "transaction history" in plan["notes"]

    def test_bulk_category_delete_has_no_single_reverse_call(self):
        plan = build_rollback(
            "delete_transaction_categories",
            {"category_ids": "cat_1, cat_2"},
            {},
            pre_state={"categories": [{"name": "A"}, {"name": "B"}]},
        )
        assert plan["reversible"] is False
        assert plan["deleted_ids"] == ["cat_1", "cat_2"]
        assert "no single reverse call" in plan["blocked_reason"]


class TestUpdateRollback:
    def test_update_without_snapshot_is_not_reversible(self):
        plan = build_rollback(
            "update_transaction",
            {"transaction_id": "txn_1", "amount": -10.0},
            {},
        )
        assert plan["reversible"] is False
        assert "values it overwrote are not known" in plan["blocked_reason"]

    def test_update_restores_only_the_fields_that_changed(self):
        plan = build_rollback(
            "update_transaction",
            {"transaction_id": "txn_1", "amount": -10.0, "notes": "new"},
            {},
            pre_state={
                "amount": -42.5,
                "notes": "lunch",
                "category_id": "cat_food",  # untouched, must not be restored
            },
        )
        assert plan["reversible"] is True
        assert plan["reverse_call"]["arguments"] == {
            "transaction_id": "txn_1",
            "amount": -42.5,
            "notes": "lunch",
        }

    def test_flags_changed_fields_absent_from_the_snapshot(self):
        plan = build_rollback(
            "update_transaction",
            {"transaction_id": "txn_1", "amount": -10.0, "goal_id": "g1"},
            {},
            pre_state={"amount": -42.5},
        )
        assert plan["reversible"] is True
        assert "goal_id" in plan["notes"]
        assert "goal_id" not in plan["reverse_call"]["arguments"]

    def test_confirmation_token_is_never_treated_as_a_changed_field(self):
        plan = build_rollback(
            "update_transaction",
            {"transaction_id": "txn_1", "amount": -10.0, "confirmation_token": "tok"},
            {},
            pre_state={"amount": -42.5},
        )
        assert "confirmation_token" not in plan["reverse_call"]["arguments"]
        assert "confirmation_token" not in plan["modified_fields"]

    def test_categorize_restores_the_previous_category(self):
        plan = build_rollback(
            "categorize_transaction",
            {"transaction_id": "txn_1", "category_id": "cat_new"},
            {},
            pre_state={"category_id": "cat_old"},
        )
        assert plan["reverse_call"] == {
            "tool": "categorize_transaction",
            "arguments": {"transaction_id": "txn_1", "category_id": "cat_old"},
        }

    def test_tagging_restores_the_previous_tag_list(self):
        plan = build_rollback(
            "add_transaction_tag",
            {"transaction_id": "txn_1", "tag_id": "tag_new"},
            {},
            pre_state={"tag_ids": ["tag_a", "tag_b"]},
        )
        assert plan["reverse_call"] == {
            "tool": "set_transaction_tags",
            "arguments": {"transaction_id": "txn_1", "tag_ids": "tag_a,tag_b"},
        }

    def test_tagging_restores_an_empty_prior_list(self):
        """A transaction that had no tags must be restorable to no tags."""
        plan = build_rollback(
            "add_transaction_tag",
            {"transaction_id": "txn_1", "tag_id": "tag_new"},
            {},
            pre_state={"tag_ids": []},
        )
        assert plan["reversible"] is True
        assert plan["reverse_call"]["arguments"]["tag_ids"] == ""

    def test_budget_restore_targets_the_same_category_and_period(self):
        plan = build_rollback(
            "set_budget_amount",
            {"category_id": "cat_1", "start_date": "2026-03-01", "amount": 500},
            {},
            pre_state={"amount": 300},
        )
        assert plan["reverse_call"]["arguments"] == {
            "category_id": "cat_1",
            "start_date": "2026-03-01",
            "amount": 300,
        }

    def test_splits_restore_serializes_prior_splits(self):
        plan = build_rollback(
            "update_transaction_splits",
            {"transaction_id": "txn_1", "splits_data": "[]"},
            {},
            pre_state={"splits": [{"amount": -10, "categoryId": "c1"}]},
        )
        assert plan["reverse_call"]["tool"] == "update_transaction_splits"
        assert "categoryId" in plan["reverse_call"]["arguments"]["splits_data"]


class TestIrreversibleOperations:
    """Operations with no inverse must say so rather than imply one."""

    @pytest.mark.parametrize(
        ("operation", "params", "expected"),
        [
            (
                "upload_account_balance_history",
                {"account_id": "acc_1"},
                "no inverse operation",
            ),
            (
                "upload_attachment",
                {"transaction_id": "txn_1"},
                "no tool for removing an attachment",
            ),
            ("some_future_tool", {}, "No rollback plan is defined"),
        ],
    )
    def test_irreversible(self, operation, params, expected):
        plan = build_rollback(operation, params, {})
        assert plan["reversible"] is False
        assert plan["reverse_call"] is None
        assert expected in plan["blocked_reason"]


def test_no_plan_ever_claims_reversible_without_a_reverse_call():
    """The invariant the whole module exists to hold.

    Swept across every operation the server guards, with and without
    snapshots, so a future branch cannot reintroduce a bare
    ``reversible: True``.
    """
    operations = [
        "create_transaction",
        "create_manual_account",
        "create_transaction_category",
        "create_tag",
        "delete_transaction",
        "delete_account",
        "delete_transaction_category",
        "delete_transaction_categories",
        "update_transaction",
        "update_account",
        "categorize_transaction",
        "add_transaction_tag",
        "set_transaction_tags",
        "set_budget_amount",
        "update_transaction_splits",
        "upload_account_balance_history",
        "upload_attachment",
    ]
    results = [None, {}, {"id": "x"}, sdk_fixtures.create_transaction_response()]
    pre_states = [None, {}, {"amount": 1}, {"tag_ids": [], "category_id": "c"}]

    for operation in operations:
        for result in results:
            for pre_state in pre_states:
                plan = build_rollback(
                    operation, {"transaction_id": "t"}, result, pre_state
                )
                if plan["reversible"]:
                    assert plan["reverse_call"] is not None, operation
                    assert plan["reverse_call"]["tool"], operation
                else:
                    assert plan["reverse_call"] is None, operation
                    assert plan.get("blocked_reason"), (
                        f"{operation} is not reversible but gives no reason"
                    )


class TestRemainingSnapshotPaths:
    def test_category_delete_recreates_with_its_icon(self):
        plan = build_rollback(
            "delete_transaction_category",
            {"category_id": "cat_1"},
            {},
            pre_state={"name": "Restaurants", "group_id": "grp_1", "icon": "🍽️"},
        )
        assert plan["reversible"] is True
        assert plan["reverse_call"] == {
            "tool": "create_transaction_category",
            "arguments": {
                "name": "Restaurants",
                "group_id": "grp_1",
                "icon": "🍽️",
            },
        }
        assert "not reassigned" in plan["notes"]

    def test_category_delete_without_a_group_is_not_reversible(self):
        plan = build_rollback(
            "delete_transaction_category",
            {"category_id": "cat_1"},
            {},
            pre_state={"name": "Restaurants"},
        )
        assert plan["reversible"] is False
        assert "lacked the fields needed" in plan["blocked_reason"]

    def test_account_delete_carries_the_subtype(self):
        plan = build_rollback(
            "delete_account",
            {"account_id": "acc_1"},
            {},
            pre_state={
                "name": "Savings",
                "account_type": "depository",
                "account_sub_type": "savings",
                "balance": 10.0,
            },
        )
        assert plan["reverse_call"]["arguments"]["account_subtype"] == "savings"

    def test_finds_an_id_inside_a_list_of_objects(self):
        """Some payloads return a list of entities rather than one."""
        result = {"createdItems": [{"id": "in_list_1"}]}
        assert extract_entity_id(result) == "in_list_1"
