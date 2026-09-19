"""Tests for asking the user, and for falling back when we cannot.

The property that matters: a confirmation token can be satisfied by the caller
alone, so it must never become reachable on a client that could have been asked
instead. Otherwise the stronger control is optional, which is the same as not
having it.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)

from monarch_mcp_server import elicitation
from monarch_mcp_server.safety_config import SafetyConfig
from monarch_mcp_server.safety_guard import SafetyGuard


@pytest.fixture
def guard(tmp_path: Path) -> SafetyGuard:
    config = SafetyConfig(config_path=str(tmp_path / "safety_config.json"))
    built = SafetyGuard(config=config)
    built.operation_log_path = str(tmp_path / "operation_log.json")
    return built


def fake_context(*, can_elicit: bool = True, result=None, raises=None):
    """A context standing in for a connected client."""
    context = MagicMock()
    context.session.check_client_capability.return_value = can_elicit
    if raises is not None:
        context.elicit = AsyncMock(side_effect=raises)
    else:
        context.elicit = AsyncMock(return_value=result)
    return context


def with_context(context):
    """Patch the context lookup that `ask_user` performs."""
    return patch(
        "fastmcp.server.dependencies.get_context",
        return_value=context,
    )


class TestAskUser:
    async def test_accepting_approves(self):
        context = fake_context(result=AcceptedElicitation(data=True))
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "a coffee")
        assert outcome.available is True
        assert outcome.accepted is True

    async def test_declining_refuses(self):
        context = fake_context(result=DeclinedElicitation())
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "a coffee")
        assert outcome.available is True
        assert outcome.accepted is False
        assert "declined" in outcome.reason

    async def test_cancelling_refuses(self):
        context = fake_context(result=CancelledElicitation())
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "a coffee")
        assert outcome.available is True
        assert outcome.accepted is False
        assert "dismissed" in outcome.reason

    async def test_answering_no_is_not_consent(self):
        """An accepted response carrying False is still a refusal.

        Treating "the user answered" as "the user agreed" would defeat the
        entire point of asking them.
        """
        context = fake_context(result=AcceptedElicitation(data=False))
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "a coffee")
        assert outcome.available is True
        assert outcome.accepted is False

    async def test_the_prompt_names_what_will_change(self):
        context = fake_context(result=AcceptedElicitation(data=True))
        with with_context(context):
            await elicitation.ask_user("delete_account", "Account 'Checking'")
        message = context.elicit.await_args.args[0]
        assert "delete_account" in message
        assert "Account 'Checking'" in message

    async def test_unavailable_when_the_client_cannot_elicit(self):
        context = fake_context(can_elicit=False)
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "a coffee")
        assert outcome.available is False
        assert outcome.accepted is False
        context.elicit.assert_not_awaited()

    async def test_unavailable_with_no_request_context(self):
        """Direct calls and startup paths have no client to ask."""
        with patch(
            "fastmcp.server.dependencies.get_context",
            side_effect=RuntimeError("No active context found."),
        ):
            outcome = await elicitation.ask_user("delete_transaction", "a coffee")
        assert outcome.available is False

    async def test_a_failing_elicitation_falls_back_rather_than_approving(self):
        context = fake_context(raises=RuntimeError("transport closed"))
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "a coffee")
        assert outcome.available is False
        assert outcome.accepted is False

    async def test_an_unrecognized_result_is_not_consent(self):
        context = fake_context(result=object())
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "a coffee")
        assert outcome.accepted is False

    async def test_a_capability_probe_that_raises_is_not_fatal(self):
        context = MagicMock()
        context.session.check_client_capability.side_effect = RuntimeError("boom")
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "a coffee")
        assert outcome.available is False


class TestGatePrefersElicitation:
    async def test_user_approval_lets_the_operation_run(self, guard):
        context = fake_context(result=AcceptedElicitation(data=True))
        with with_context(context):
            allowed, refusal = await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t1"}, None
            )
        assert allowed is True
        assert refusal is None

    async def test_user_refusal_issues_no_token(self, guard):
        """The crux. A refusal that handed back a token would let the caller
        approve what the user just declined."""
        context = fake_context(result=DeclinedElicitation())
        with with_context(context):
            allowed, refusal = await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t1"}, None
            )

        assert allowed is False
        assert refusal["error"] == "Not approved"
        assert "confirmation_token" not in refusal
        assert guard.approvals.pending_count() == 0

    async def test_no_token_is_minted_when_the_user_can_be_asked(self, guard):
        """On an elicitation-capable client the weaker path never exists."""
        context = fake_context(result=AcceptedElicitation(data=True))
        with with_context(context):
            await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t1"}, None
            )
        assert guard.approvals.pending_count() == 0

    async def test_falls_back_to_a_token_when_the_client_cannot_elicit(self, guard):
        context = fake_context(can_elicit=False)
        with with_context(context):
            allowed, refusal = await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t1"}, None
            )

        assert allowed is False
        assert refusal["error"] == "Confirmation required"
        assert refusal["confirmation_token"]
        assert guard.approvals.pending_count() == 1

    async def test_the_fallback_token_still_works_end_to_end(self, guard):
        context = fake_context(can_elicit=False)
        params = {"transaction_id": "t1"}
        with with_context(context):
            _, refusal = await guard.confirm_operation(
                "delete_transaction", params, None
            )
            allowed, second = await guard.confirm_operation(
                "delete_transaction",
                {**params, "confirmation_token": refusal["confirmation_token"]},
                None,
            )
        assert allowed is True
        assert second is None

    async def test_the_preview_reaches_the_user(self, guard):
        """The snapshot is why the prompt is answerable rather than opaque."""
        context = fake_context(result=AcceptedElicitation(data=True))
        pre_state = {
            "merchant_name": "Cafe Example",
            "amount": -42.5,
            "date": "2026-03-04",
            "category_id": "cat_food",
        }
        with with_context(context):
            await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t1"}, pre_state
            )
        message = context.elicit.await_args.args[0]
        assert "Cafe Example" in message
        assert "-42.5" in message

    async def test_non_destructive_operations_are_never_elicited(self, guard):
        context = fake_context(result=AcceptedElicitation(data=True))
        with with_context(context):
            allowed, _ = await guard.confirm_operation(
                "create_transaction", {"amount": 1}, None
            )
        assert allowed is True
        context.elicit.assert_not_awaited()

    async def test_disabling_confirmation_skips_the_prompt(self, guard):
        guard.config.config["require_confirmation"] = False
        context = fake_context(result=AcceptedElicitation(data=True))
        with with_context(context):
            allowed, _ = await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t1"}, None
            )
        assert allowed is True
        context.elicit.assert_not_awaited()


class TestPromptChoices:
    """The prompt offers a way to stop being asked, and names its scope."""

    async def test_offers_once_grant_and_decline(self):
        context = fake_context(result=AcceptedElicitation(data="Approve once"))
        with with_context(context):
            await elicitation.ask_user("delete_transaction", "a coffee", 900)

        choices = context.elicit.await_args.kwargs["response_type"]
        assert choices == [
            "Approve once",
            "Approve all delete_transaction for 15 minutes",
            "Decline",
        ]

    async def test_the_grant_option_names_the_operation(self):
        """Its scope is the operation, so the wording has to say which."""
        context = fake_context(result=AcceptedElicitation(data="Approve once"))
        with with_context(context):
            await elicitation.ask_user("delete_account", "an account", 900)

        grant_option = context.elicit.await_args.kwargs["response_type"][1]
        assert "delete_account" in grant_option

    async def test_zero_seconds_removes_the_option(self):
        """Operators who want every call confirmed individually can have it."""
        context = fake_context(result=AcceptedElicitation(data="Approve once"))
        with with_context(context):
            await elicitation.ask_user("delete_transaction", "a coffee", 0)

        assert context.elicit.await_args.kwargs["response_type"] == [
            "Approve once",
            "Decline",
        ]


class TestInterpretingTheAnswer:
    async def test_approve_once_grants_nothing(self):
        context = fake_context(result=AcceptedElicitation(data="Approve once"))
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "x", 900)
        assert outcome.accepted is True
        assert outcome.grant_seconds == 0

    async def test_choosing_the_grant_returns_its_duration(self):
        answer = "Approve all delete_transaction for 15 minutes"
        context = fake_context(result=AcceptedElicitation(data=answer))
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "x", 900)
        assert outcome.accepted is True
        assert outcome.grant_seconds == 900

    async def test_declining_grants_nothing(self):
        context = fake_context(result=AcceptedElicitation(data="Decline"))
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "x", 900)
        assert outcome.accepted is False
        assert outcome.grant_seconds == 0

    async def test_a_grant_answer_for_another_operation_is_not_honoured(self):
        """A grant string only means what it says for the operation it names."""
        answer = "Approve all delete_account for 15 minutes"
        context = fake_context(result=AcceptedElicitation(data=answer))
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "x", 900)
        assert outcome.accepted is False
        assert outcome.grant_seconds == 0

    async def test_an_unexpected_answer_is_not_consent(self):
        context = fake_context(result=AcceptedElicitation(data="Sure, go ahead"))
        with with_context(context):
            outcome = await elicitation.ask_user("delete_transaction", "x", 900)
        assert outcome.accepted is False

    async def test_a_bool_answer_is_still_honoured(self):
        """A client answering the older shape must not be misread."""
        for value, expected in ((True, True), (False, False)):
            context = fake_context(result=AcceptedElicitation(data=value))
            with with_context(context):
                outcome = await elicitation.ask_user("delete_transaction", "x", 900)
            assert outcome.accepted is expected
            assert outcome.grant_seconds == 0


class TestGateHonoursGrants:
    async def test_a_grant_stops_the_prompting(self, guard):
        answer = "Approve all delete_transaction for 15 minutes"
        context = fake_context(result=AcceptedElicitation(data=answer))

        with with_context(context):
            allowed, _ = await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t1"}, None
            )
            assert allowed is True
            assert context.elicit.await_count == 1

            # The next two calls are covered and must not ask again.
            for txn in ("t2", "t3"):
                allowed, refusal = await guard.confirm_operation(
                    "delete_transaction", {"transaction_id": txn}, None
                )
                assert allowed is True
                assert refusal is None

        assert context.elicit.await_count == 1

    async def test_a_grant_does_not_cover_a_different_operation(self, guard):
        """The safety boundary, end to end through the gate."""
        answer = "Approve all delete_transaction for 15 minutes"
        context = fake_context(result=AcceptedElicitation(data=answer))

        with with_context(context):
            await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t1"}, None
            )
            # A different destructive operation must still be asked about.
            context.elicit.return_value = AcceptedElicitation(data="Decline")
            allowed, refusal = await guard.confirm_operation(
                "delete_account", {"account_id": "a1"}, None
            )

        assert allowed is False
        assert refusal["error"] == "Not approved"
        assert context.elicit.await_count == 2

    async def test_approve_once_does_not_cover_the_next_call(self, guard):
        context = fake_context(result=AcceptedElicitation(data="Approve once"))
        with with_context(context):
            await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t1"}, None
            )
            await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t2"}, None
            )
        assert context.elicit.await_count == 2

    async def test_an_expired_grant_asks_again(self, guard):
        import time as _time

        answer = "Approve all delete_transaction for 15 minutes"
        context = fake_context(result=AcceptedElicitation(data=answer))
        with with_context(context):
            await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t1"}, None
            )
            guard.grants._granted["delete_transaction"] = _time.time() - 1
            await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t2"}, None
            )
        assert context.elicit.await_count == 2

    async def test_the_token_fallback_can_never_create_a_grant(self, guard):
        """A token is answered by the caller. Letting one mint a standing
        approval would hand an agent the power to stop being asked."""
        context = fake_context(can_elicit=False)
        params = {"transaction_id": "t1"}

        with with_context(context):
            _, refusal = await guard.confirm_operation(
                "delete_transaction", params, None
            )
            await guard.confirm_operation(
                "delete_transaction",
                {**params, "confirmation_token": refusal["confirmation_token"]},
                None,
            )

        assert guard.grants.active() == {}

    async def test_daily_caps_still_apply_under_a_grant(self, guard):
        """A grant silences the prompt; it does not raise the ceiling."""
        guard.config.config["daily_limits"] = {"delete_transaction": 1}
        guard.grants.grant("delete_transaction", 900)

        guard.record_operation("delete_transaction", success=True)

        allowed, message = guard.check_operation("delete_transaction", {})
        assert allowed is False
        assert "Daily limit reached" in message

    async def test_disabling_grants_means_every_call_is_asked(self, guard):
        guard.config.config["approval_grant_seconds"] = 0
        context = fake_context(result=AcceptedElicitation(data="Approve once"))

        with with_context(context):
            await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t1"}, None
            )
            choices = context.elicit.await_args.kwargs["response_type"]
            await guard.confirm_operation(
                "delete_transaction", {"transaction_id": "t2"}, None
            )

        assert choices == ["Approve once", "Decline"]
        assert context.elicit.await_count == 2
