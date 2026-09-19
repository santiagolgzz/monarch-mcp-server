"""Tests for the two-step confirmation gate and the daily caps.

Issue #20: ``require_approval`` named five operations and gated none of them.
``check_operation`` returned True for that branch, so a "destructive" call ran
exactly like a warned one while ``get_safety_stats`` reported
``approval_required_for`` as though a gate existed.

The properties that make the gate worth having, rather than a rubber stamp:
a token works once, only for the call it was issued against, and only before
it expires — and the challenge says what is about to be destroyed.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from monarch_mcp_server.approval import ApprovalStore, fingerprint, summarize
from monarch_mcp_server.safety_config import SafetyConfig
from monarch_mcp_server.safety_guard import SafetyGuard


@pytest.fixture
def guard(tmp_path: Path) -> SafetyGuard:
    config = SafetyConfig(config_path=str(tmp_path / "safety_config.json"))
    built = SafetyGuard(config=config)
    built.operation_log_path = str(tmp_path / "operation_log.json")
    return built


class TestFingerprint:
    def test_same_call_hashes_alike(self):
        a = fingerprint("delete_transaction", {"transaction_id": "t1"})
        b = fingerprint("delete_transaction", {"transaction_id": "t1"})
        assert a == b

    def test_different_targets_hash_differently(self):
        a = fingerprint("delete_transaction", {"transaction_id": "t1"})
        b = fingerprint("delete_transaction", {"transaction_id": "t2"})
        assert a != b

    def test_different_operations_hash_differently(self):
        assert fingerprint("delete_transaction", {"id": "x"}) != fingerprint(
            "delete_account", {"id": "x"}
        )

    def test_the_token_itself_is_excluded(self):
        """The requesting call has no token and the redeeming call does; if
        the token counted, the two could never match."""
        without = fingerprint("delete_transaction", {"transaction_id": "t1"})
        with_token = fingerprint(
            "delete_transaction", {"transaction_id": "t1", "confirmation_token": "abc"}
        )
        assert without == with_token

    def test_key_order_does_not_matter(self):
        a = fingerprint("op", {"a": 1, "b": 2})
        b = fingerprint("op", {"b": 2, "a": 1})
        assert a == b


class TestApprovalStore:
    def test_a_fresh_token_is_accepted_once(self):
        store = ApprovalStore()
        params = {"transaction_id": "t1"}
        challenge = store.issue("delete_transaction", params, "a transaction")

        accepted, _ = store.redeem(challenge.token, "delete_transaction", params)
        assert accepted is True

        # Single use: the same token must not work twice.
        accepted, reason = store.redeem(challenge.token, "delete_transaction", params)
        assert accepted is False
        assert "not recognized" in reason

    def test_a_token_cannot_be_spent_on_a_different_record(self):
        """The property that makes confirmation meaningful."""
        store = ApprovalStore()
        challenge = store.issue(
            "delete_transaction", {"transaction_id": "t1"}, "transaction one"
        )

        accepted, reason = store.redeem(
            challenge.token, "delete_transaction", {"transaction_id": "t2"}
        )
        assert accepted is False
        assert "different arguments" in reason

    def test_a_token_cannot_be_spent_on_a_different_operation(self):
        store = ApprovalStore()
        challenge = store.issue("delete_transaction", {"id": "x"}, "something")

        accepted, reason = store.redeem(challenge.token, "delete_account", {"id": "x"})
        assert accepted is False
        assert "issued for delete_transaction" in reason

    def test_an_expired_token_is_refused(self):
        store = ApprovalStore(ttl_seconds=1)
        params = {"transaction_id": "t1"}
        challenge = store.issue("delete_transaction", params, "a transaction")

        # Age the challenge rather than sleeping through its TTL.
        store._pending[challenge.token] = type(challenge)(
            token=challenge.token,
            operation=challenge.operation,
            fingerprint=challenge.fingerprint,
            expires_at=time.time() - 1,
            preview=challenge.preview,
        )

        accepted, reason = store.redeem(challenge.token, "delete_transaction", params)
        assert accepted is False
        assert "expired" in reason

    def test_an_unknown_token_is_refused(self):
        store = ApprovalStore()
        accepted, _ = store.redeem("never-issued", "delete_transaction", {})
        assert accepted is False

    def test_pending_challenges_are_bounded(self):
        """An abandoning caller must not grow the store without limit."""
        store = ApprovalStore()
        for index in range(200):
            store.issue("delete_transaction", {"transaction_id": str(index)}, "x")
        assert store.pending_count() <= 64


class TestSummarize:
    def test_describes_the_transaction_being_deleted(self):
        text = summarize(
            "delete_transaction",
            {"transaction_id": "t1"},
            {
                "merchant_name": "Cafe Example",
                "amount": -42.5,
                "date": "2026-03-04",
                "category_id": "cat_food",
            },
        )
        assert "Cafe Example" in text
        assert "-42.5" in text
        assert "2026-03-04" in text

    def test_warns_that_account_history_is_lost(self):
        text = summarize(
            "delete_account",
            {"account_id": "a1"},
            {"name": "Checking", "account_type": "depository", "balance": 100.0},
        )
        assert "Checking" in text
        assert "not be recoverable" in text

    def test_counts_the_categories_in_a_bulk_delete(self):
        text = summarize(
            "delete_transaction_categories",
            {"category_ids": "c1,c2"},
            {"categories": [{"name": "A"}, {"name": "B"}]},
        )
        assert "2 categories" in text
        assert "A, B" in text

    def test_says_so_when_nothing_could_be_captured(self):
        text = summarize("delete_transaction", {"transaction_id": "t1"}, None)
        assert "t1" in text
        assert "not be reversible" in text


class TestGuardConfirmation:
    async def test_non_approval_operations_pass_straight_through(self, guard):
        confirmed, refusal = await guard.confirm_operation(
            "create_transaction", {"amount": 1}, None
        )
        assert confirmed is True
        assert refusal is None

    async def test_challenge_carries_the_preview(self, guard):
        confirmed, refusal = await guard.confirm_operation(
            "delete_transaction",
            {"transaction_id": "t1"},
            {
                "merchant_name": "Cafe Example",
                "amount": -42.5,
                "date": "2026-03-04",
                "category_id": "cat_food",
            },
        )
        assert confirmed is False
        assert "Cafe Example" in refusal["about_to_change"]
        assert refusal["expires_in_seconds"] > 0

    async def test_a_rejected_token_explains_itself(self, guard):
        confirmed, refusal = await guard.confirm_operation(
            "delete_transaction",
            {"transaction_id": "t1", "confirmation_token": "bogus"},
            None,
        )
        assert confirmed is False
        assert refusal["error"] == "Confirmation rejected"
        assert refusal["reason"]

    async def test_the_gate_can_be_turned_off(self, guard):
        guard.config.config["require_confirmation"] = False
        confirmed, refusal = await guard.confirm_operation(
            "delete_transaction", {"transaction_id": "t1"}, None
        )
        assert confirmed is True
        assert refusal is None

    def test_stats_report_the_gate_honestly(self, guard):
        """get_safety_stats advertised approval_required_for while nothing
        was gated. It must now say whether the gate is on."""
        stats = guard.get_operation_stats()
        assert stats["confirmation_required"] is True
        assert "delete_transaction" in stats["approval_required_for"]

        guard.config.config["require_confirmation"] = False
        assert guard.get_operation_stats()["confirmation_required"] is False


class TestDailyLimits:
    def test_under_the_limit_is_allowed(self, guard):
        guard.config.config["daily_limits"] = {"delete_transaction": 3}
        allowed, _ = guard.check_operation("delete_transaction", {})
        assert allowed is True

    def test_the_limit_blocks_once_reached(self, guard):
        guard.config.config["daily_limits"] = {"delete_transaction": 2}

        for _ in range(2):
            allowed, _ = guard.check_operation("delete_transaction", {})
            assert allowed is True
            guard.record_operation("delete_transaction", success=True)

        allowed, message = guard.check_operation("delete_transaction", {})
        assert allowed is False
        assert "Daily limit reached" in message
        assert "2/2" in message
        # The message must say how to proceed deliberately.
        assert "daily_limits.delete_transaction" in message

    def test_failures_do_not_consume_the_budget(self, guard):
        """Only successful writes count, so a flapping upstream cannot
        exhaust the day's allowance."""
        guard.config.config["daily_limits"] = {"delete_transaction": 1}

        guard.record_operation("delete_transaction", success=False, error="boom")

        allowed, _ = guard.check_operation("delete_transaction", {})
        assert allowed is True

    def test_uncapped_operations_are_unaffected(self, guard):
        guard.config.config["daily_limits"] = {}
        for _ in range(50):
            guard.record_operation("create_transaction", success=True)
        allowed, _ = guard.check_operation("create_transaction", {})
        assert allowed is True

    def test_emergency_stop_still_takes_precedence(self, guard):
        guard.config.config["daily_limits"] = {"delete_transaction": 99}
        guard.config.config["emergency_stop"] = True
        allowed, message = guard.check_operation("delete_transaction", {})
        assert allowed is False
        assert "EMERGENCY STOP" in message

    @pytest.mark.parametrize("bad", ["not a number", None, -1])
    def test_malformed_limits_are_treated_as_no_limit(self, guard, bad):
        guard.config.config["daily_limits"] = {"delete_transaction": bad}
        allowed, _ = guard.check_operation("delete_transaction", {})
        assert allowed is True

    def test_a_zero_limit_blocks_immediately(self, guard):
        """Zero is a real setting: disable this operation for today."""
        guard.config.config["daily_limits"] = {"delete_transaction": 0}
        allowed, message = guard.check_operation("delete_transaction", {})
        assert allowed is False
        assert "Daily limit reached" in message


class TestSummarizeRemainingShapes:
    """The preview is the only thing a user sees before confirming, so every
    destructive operation must produce a readable one."""

    def test_describes_a_single_category(self):
        text = summarize(
            "delete_transaction_category",
            {"category_id": "c1"},
            {"name": "Restaurants", "group_id": "grp_spending"},
        )
        assert "Restaurants" in text
        assert "grp_spending" in text

    def test_falls_back_to_the_snapshot_for_unlisted_operations(self):
        text = summarize(
            "upload_account_balance_history",
            {"account_id": "a1"},
            {"rows": 1200},
        )
        assert "upload_account_balance_history" in text
        assert "1200" in text

    def test_preview_never_raises(self):
        """A malformed snapshot must not break the gate it describes."""
        from monarch_mcp_server.approval import preview_of

        class Exploding(dict):
            def get(self, *args, **kwargs):
                raise RuntimeError("boom")

        text = preview_of("delete_transaction", {}, Exploding({"a": 1}))
        assert "delete_transaction" in text
        assert "details unavailable" in text


class TestSafetyConfigRobustness:
    """The config is a JSON file users edit by hand, so bad values must
    degrade to safe defaults rather than crash a write path."""

    def test_an_existing_config_file_keeps_new_defaults(self, tmp_path):
        """Upgrading must not leave an older config without the new gate."""
        path = tmp_path / "safety_config.json"
        path.write_text('{"emergency_stop": false}')

        config = SafetyConfig(config_path=str(path))

        assert config.confirmation_enabled() is True
        assert config.daily_limit("delete_transaction") == 50
        assert "delete_transaction" in config.config["require_approval"]

    def test_a_corrupt_config_file_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "safety_config.json"
        path.write_text("{not json at all")

        config = SafetyConfig(config_path=str(path))

        assert config.confirmation_enabled() is True
        assert config.requires_approval("delete_transaction") is True

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(600, 600), ("900", 900), (0, 300), (-5, 300), ("soon", 300), (None, 300)],
    )
    def test_confirmation_ttl_rejects_nonsense(self, tmp_path, value, expected):
        config = SafetyConfig(config_path=str(tmp_path / "c.json"))
        config.config["confirmation_ttl_seconds"] = value
        assert config.confirmation_ttl() == expected

    def test_saving_to_an_unwritable_path_does_not_raise(self, tmp_path):
        """Emergency stop calls save_config; it must not blow up mid-incident."""
        config = SafetyConfig(config_path="/proc/nonexistent/safety_config.json")
        config.config["emergency_stop"] = True
        config.save_config()  # logs, does not raise
