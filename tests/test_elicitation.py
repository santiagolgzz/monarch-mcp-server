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
