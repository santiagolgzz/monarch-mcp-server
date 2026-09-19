"""Two-step confirmation for destructive operations.

``SafetyConfig`` has always had a ``require_approval`` list, and
``get_safety_stats`` has always reported ``approval_required_for``. Neither did
anything: ``check_operation`` returned True for that branch, so the five
"destructive" operations executed exactly like the warned ones. Anyone reading
the config would reasonably conclude a gate existed (issue #20).

A gate could not simply be switched on, because MCP has no out-of-band approval
channel — refusing outright would make those five tools permanently unusable.
So the gate lives inside the request/response cycle:

1. The first call arrives without a token. It is refused, and the refusal
   carries a challenge: a token, how long it lasts, and a summary of the record
   that is about to be destroyed, taken from the pre-operation snapshot.
2. The caller repeats the call with ``confirmation_token`` set.

The token is bound to the operation *and its arguments*, so one issued for
``delete_transaction(txn_1)`` cannot be spent on ``txn_2``. It is single-use
and expires, so a token cannot be held and replayed later.

Tokens live in memory only. A restart clears them, which fails closed: the
worst outcome is that a caller has to re-confirm.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300

# A caller that abandons confirmations should not grow this without bound.
_MAX_PENDING = 64


def fingerprint(operation_name: str, params: dict) -> str:
    """Stable hash of an operation and its arguments.

    Binding a token to this is what stops a confirmation for one record being
    spent on another. ``confirmation_token`` itself is excluded, since it is
    absent on the call that requests the challenge and present on the call that
    redeems it — including it would mean the two never match.
    """
    material = {
        key: value for key, value in params.items() if key != "confirmation_token"
    }
    encoded = json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha256(f"{operation_name}|{encoded}".encode()).hexdigest()


@dataclass(frozen=True)
class Challenge:
    """A pending confirmation."""

    token: str
    operation: str
    fingerprint: str
    expires_at: float
    preview: str

    def as_response(self) -> dict:
        """The refusal an unconfirmed caller receives."""
        remaining = max(0, int(self.expires_at - time.time()))
        return {
            "error": "Confirmation required",
            "operation": self.operation,
            "about_to_change": self.preview,
            "confirmation_token": self.token,
            "expires_in_seconds": remaining,
            "how_to_proceed": (
                f"Repeat the same {self.operation} call with "
                f"confirmation_token={self.token!r} to carry it out. The token "
                f"works once, only for these exact arguments, and expires in "
                f"{remaining}s. Do not reuse it for a different record."
            ),
        }


class ApprovalStore:
    """Issues and redeems confirmation tokens."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self._pending: dict[str, Challenge] = {}

    def _purge_expired(self, now: float) -> None:
        expired = [
            token
            for token, challenge in self._pending.items()
            if challenge.expires_at <= now
        ]
        for token in expired:
            del self._pending[token]

    def issue(self, operation_name: str, params: dict, preview: str) -> Challenge:
        """Create a challenge for an operation awaiting confirmation."""
        now = time.time()
        self._purge_expired(now)

        # Bound the store even if every challenge is abandoned unexpired.
        if len(self._pending) >= _MAX_PENDING:
            oldest = min(self._pending.values(), key=lambda c: c.expires_at)
            del self._pending[oldest.token]

        challenge = Challenge(
            token=secrets.token_urlsafe(16),
            operation=operation_name,
            fingerprint=fingerprint(operation_name, params),
            expires_at=now + self.ttl_seconds,
            preview=preview,
        )
        self._pending[challenge.token] = challenge
        logger.info(
            "Confirmation required for %s; issued a token valid for %ss",
            operation_name,
            self.ttl_seconds,
        )
        return challenge

    def redeem(self, token: str, operation_name: str, params: dict) -> tuple[bool, str]:
        """Spend a token. Returns ``(accepted, reason)``.

        A token is accepted once, for the operation and arguments it was issued
        against, before it expires. Every rejection explains itself, because a
        caller that cannot tell "expired" from "wrong record" will just retry
        the wrong thing.
        """
        now = time.time()
        self._purge_expired(now)

        challenge = self._pending.get(token)
        if challenge is None:
            return False, (
                "That confirmation token is not recognized. It may have "
                "expired, already been used, or been issued before a restart. "
                "Repeat the call without a token to get a new one."
            )

        if challenge.operation != operation_name:
            return False, (
                f"That token was issued for {challenge.operation}, not "
                f"{operation_name}."
            )

        if challenge.fingerprint != fingerprint(operation_name, params):
            return False, (
                "That token was issued for different arguments. A confirmation "
                "applies only to the exact call it was requested for — request "
                "a new token for this one."
            )

        # Single use: spend it whether or not the operation then succeeds, so a
        # failed destructive call cannot be silently retried on the same token.
        del self._pending[token]
        return True, "Confirmed"

    def pending_count(self) -> int:
        """How many confirmations are outstanding, for diagnostics."""
        self._purge_expired(time.time())
        return len(self._pending)


def summarize(operation_name: str, params: dict, pre_state: dict | None) -> str:
    """Describe what an operation is about to destroy.

    A token the caller cannot evaluate is a rubber stamp, so the challenge
    names the actual record rather than echoing an opaque ID.
    """
    if not pre_state:
        target = (
            params.get("transaction_id")
            or params.get("account_id")
            or params.get("category_id")
            or params.get("category_ids")
            or "the target record"
        )
        return (
            f"{operation_name} on {target}. No snapshot of it could be taken, "
            "so its contents are unknown and this will not be reversible."
        )

    if operation_name == "delete_transaction":
        return (
            f"Transaction {pre_state.get('merchant_name')!r} "
            f"for {pre_state.get('amount')} on {pre_state.get('date')} "
            f"(category {pre_state.get('category_id')})"
        )

    if operation_name == "delete_account":
        return (
            f"Account {pre_state.get('name')!r} "
            f"({pre_state.get('account_type')}) with balance "
            f"{pre_state.get('balance')}. Its transaction history will not be "
            "recoverable."
        )

    if operation_name == "delete_transaction_category":
        return (
            f"Category {pre_state.get('name')!r} in group {pre_state.get('group_id')}"
        )

    if operation_name == "delete_transaction_categories":
        names = [c.get("name") for c in pre_state.get("categories") or []]
        return f"{len(names)} categories: {', '.join(str(n) for n in names)}"

    return f"{operation_name} with {json.dumps(pre_state, default=str)[:300]}"


def preview_of(operation_name: str, params: dict, pre_state: dict | None) -> str:
    """Public entry point for building a challenge preview."""
    try:
        return summarize(operation_name, params, pre_state)
    except Exception:  # noqa: BLE001 - a preview must never break the gate
        logger.debug("Failed to summarize %s", operation_name, exc_info=True)
        return f"{operation_name} (details unavailable)"
