"""Ask the person, not the caller, before destroying something.

The confirmation tokens in `approval.py` are in-band: the server refuses, hands
back a token, and the caller repeats the call with it. That stops accidents and
argument drift, but it proves nothing about a human. The same agent that asked
to delete a transaction receives the token and can hand it straight back. A
runaway agent confirms its own deletes; it just takes two round-trips.

MCP has the mechanism this needs. `elicitation/create` lets a server ask the
client to put a question to the user mid-request and return their answer, so
approval comes from a person rather than from the caller echoing a value back.

Elicitation is a client capability, so it cannot be the only path — a server
that depends on it breaks on every client that has not implemented it. The gate
therefore prefers elicitation and falls back to a token:

1. A token the caller supplies is redeemed, because this server issued it.
2. Otherwise, ask the user through the client. Accept proceeds; decline and
   cancel refuse, and no token is issued, so there is nothing to replay.
3. If the client cannot elicit — or elicitation fails — fall back to issuing a
   token challenge.

On an elicitation-capable client no token is ever minted, so the weaker path
cannot be used to sidestep the stronger one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ElicitationOutcome:
    """What asking the user produced.

    ``available`` is False when the client cannot be asked at all, which is the
    signal to fall back to a token rather than to treat it as a refusal.

    ``grant_seconds`` is set when the user chose to stop being asked for a
    while. It is only ever non-zero on an approval that came from a person.
    """

    available: bool
    accepted: bool = False
    reason: str = ""
    grant_seconds: int = 0


UNAVAILABLE = ElicitationOutcome(available=False)

APPROVE_ONCE = "Approve once"
DECLINE = "Decline"


def grant_choice(operation_name: str, seconds: int) -> str:
    """The wording of the "stop asking" option.

    It names the operation, because that is the whole scope of the grant, and
    the duration, because an open-ended one would be a different decision.
    """
    minutes = max(1, round(seconds / 60))
    unit = "minute" if minutes == 1 else "minutes"
    return f"Approve all {operation_name} for {minutes} {unit}"


def _client_can_elicit(context) -> bool:
    """Whether the connected client declared the elicitation capability."""
    try:
        from mcp.types import ClientCapabilities, ElicitationCapability

        return bool(
            context.session.check_client_capability(
                ClientCapabilities(elicitation=ElicitationCapability())
            )
        )
    except Exception:  # noqa: BLE001 - capability probing must never raise
        logger.debug("Could not read client capabilities", exc_info=True)
        return False


def _prompt(operation_name: str, preview: str) -> str:
    """The question the user actually sees."""
    return (
        f"{operation_name} is about to run and cannot be undone automatically "
        f"unless a snapshot was captured.\n\n"
        f"About to change: {preview}\n\n"
        f"Approve this?"
    )


def _choices(operation_name: str, grant_seconds: int) -> list[str]:
    """Options offered in the prompt, most conservative first."""
    options = [APPROVE_ONCE]
    if grant_seconds > 0:
        options.append(grant_choice(operation_name, grant_seconds))
    options.append(DECLINE)
    return options


async def ask_user(
    operation_name: str, preview: str, grant_seconds: int = 0
) -> ElicitationOutcome:
    """Ask the person to approve a destructive operation.

    Args:
        operation_name: The operation awaiting approval.
        preview: What it is about to change, from the pre-operation snapshot.
        grant_seconds: When positive, the prompt also offers to stop asking for
            this operation for that long. Zero omits the option entirely, so
            every call is asked about individually.

    Returns ``UNAVAILABLE`` when there is no client to ask — no active request
    context, no declared capability, or the attempt failed. Callers treat that
    as "use the fallback", never as approval.
    """
    try:
        from fastmcp.server.dependencies import get_context

        context = get_context()
    except Exception:  # noqa: BLE001 - no request context (e.g. direct call)
        logger.debug("No active MCP context; cannot elicit", exc_info=True)
        return UNAVAILABLE

    if not _client_can_elicit(context):
        return UNAVAILABLE

    try:
        from fastmcp.server.elicitation import (
            AcceptedElicitation,
            CancelledElicitation,
            DeclinedElicitation,
        )

        # A list of strings becomes an enum schema, which clients render as
        # discrete choices rather than a free-text box or an empty form.
        choices = _choices(operation_name, grant_seconds)
        result = await context.elicit(
            _prompt(operation_name, preview), response_type=choices
        )
    except Exception as exc:  # noqa: BLE001 - never let this block the gate
        logger.warning(
            "Elicitation failed for %s (%s); falling back to a confirmation token.",
            operation_name,
            exc,
        )
        return UNAVAILABLE

    if isinstance(result, AcceptedElicitation):
        return _interpret(result.data, operation_name, grant_seconds)

    if isinstance(result, DeclinedElicitation):
        return ElicitationOutcome(
            available=True, accepted=False, reason="The user declined."
        )

    if isinstance(result, CancelledElicitation):
        return ElicitationOutcome(
            available=True,
            accepted=False,
            reason="The user dismissed the prompt without answering.",
        )

    # An unrecognized result is not consent.
    logger.warning(
        "Unrecognized elicitation result %r for %s; treating as not approved.",
        type(result).__name__,
        operation_name,
    )
    return ElicitationOutcome(
        available=True,
        accepted=False,
        reason="The client returned an unrecognized response.",
    )


def _interpret(
    answer: object, operation_name: str, grant_seconds: int
) -> ElicitationOutcome:
    """Turn the user's choice into an outcome.

    Anything that is not recognisably an approval is treated as a refusal. The
    act of answering is not consent, so an unexpected payload must never open
    the gate.
    """
    # Older prompts used a bool; keep honouring it so a client that answers
    # that way is not misread as approving.
    if isinstance(answer, bool):
        return ElicitationOutcome(
            available=True,
            accepted=answer,
            reason="Approved by the user" if answer else "The user answered no.",
        )

    if answer == APPROVE_ONCE:
        return ElicitationOutcome(
            available=True, accepted=True, reason="Approved by the user, once."
        )

    if grant_seconds > 0 and answer == grant_choice(operation_name, grant_seconds):
        return ElicitationOutcome(
            available=True,
            accepted=True,
            reason=f"Approved by the user for {grant_seconds}s.",
            grant_seconds=grant_seconds,
        )

    if answer == DECLINE:
        return ElicitationOutcome(
            available=True, accepted=False, reason="The user declined."
        )

    logger.warning(
        "Unrecognized elicitation answer %r for %s; treating as not approved.",
        answer,
        operation_name,
    )
    return ElicitationOutcome(
        available=True,
        accepted=False,
        reason="The client returned an unrecognized answer.",
    )
