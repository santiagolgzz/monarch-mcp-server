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
    """

    available: bool
    accepted: bool = False
    reason: str = ""


UNAVAILABLE = ElicitationOutcome(available=False)


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


async def ask_user(operation_name: str, preview: str) -> ElicitationOutcome:
    """Ask the person to approve a destructive operation.

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

        # `bool` rather than an empty schema: some clients render an empty form
        # as an unanswerable prompt.
        result = await context.elicit(
            _prompt(operation_name, preview), response_type=bool
        )
    except Exception as exc:  # noqa: BLE001 - never let this block the gate
        logger.warning(
            "Elicitation failed for %s (%s); falling back to a confirmation token.",
            operation_name,
            exc,
        )
        return UNAVAILABLE

    if isinstance(result, AcceptedElicitation):
        # An accept whose payload is an explicit False is a "no". Treating the
        # act of answering as consent would defeat the point of asking.
        approved = result.data is not False
        return ElicitationOutcome(
            available=True,
            accepted=approved,
            reason="Approved by the user" if approved else "The user answered no.",
        )

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
