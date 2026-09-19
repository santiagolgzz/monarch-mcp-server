"""Rollback planning for write operations.

The audit log's job is to let an operator undo something. That only works if
the log holds the data an undo actually needs, so this module never claims an
operation is reversible on the strength of its name. ``reversible`` is computed
from whether a concrete reverse call could be built, and when one could not,
``blocked_reason`` says what was missing.

Two shapes of undo exist:

* **Creates** are reversible from the result alone — delete what was made — so
  they need the new entity's ID.
* **Deletes and updates** are reversible only from state captured *before* the
  operation ran, because the operation is what destroyed it. See
  ``pre_state.py``.

Everything here is pure: it takes parameters, a result, and an optional
pre-state snapshot, and returns a plan. Nothing calls Monarch.
"""

from __future__ import annotations

import json
from typing import Any

# Keys whose subtrees never hold the created entity's ID. GraphQL payloads put
# an `errors` sibling next to the entity, and its objects carry `message` and
# `code` — no `id` — but skipping them keeps the search honest if that changes.
_ID_SEARCH_SKIP_KEYS = frozenset({"errors", "__typename"})

# Checked in order at each level of the breadth-first search.
_ID_FIELDS = ("id", "transaction_id", "account_id", "category_id", "tag_id")

# How deep to search a result for an ID. Real payloads nest two levels
# (mutation -> entity -> id); the bound stops a pathological result from
# turning the audit write into a long walk.
_MAX_ID_SEARCH_DEPTH = 6


def extract_entity_id(result: Any) -> str | None:
    """Find the ID of the entity an operation created.

    The SDK returns GraphQL envelopes, so the ID is not at the top level::

        {"createTransaction": {"transaction": {"id": "txn_1"}, "errors": None}}

    Searching breadth-first returns the shallowest ID, which is the entity the
    operation acted on rather than something nested inside it — a transaction's
    own ID rather than its category's. Returns None when the result carries no
    ID, which is what a failed mutation looks like.
    """
    if result is None:
        return None

    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, ValueError):
            return None

    if not isinstance(result, dict):
        return None

    level: list[dict] = [result]
    for _ in range(_MAX_ID_SEARCH_DEPTH):
        if not level:
            return None

        for node in level:
            for field in _ID_FIELDS:
                value = node.get(field)
                if value is not None and not isinstance(value, dict | list):
                    return str(value)

        next_level: list[dict] = []
        for node in level:
            for key, value in node.items():
                if key in _ID_SEARCH_SKIP_KEYS:
                    continue
                if isinstance(value, dict):
                    next_level.append(value)
                elif isinstance(value, list):
                    next_level.extend(item for item in value if isinstance(item, dict))
        level = next_level

    return None


def payload_errors(result: Any) -> list[Any]:
    """Return any GraphQL payload errors carried alongside a mutation result.

    Monarch reports business-level failures in an ``errors`` field rather than
    by raising, so a call can "succeed" and still have changed nothing.
    """
    if not isinstance(result, dict):
        return []

    found: list[Any] = []
    stack: list[dict] = [result]
    depth = 0
    while stack and depth < _MAX_ID_SEARCH_DEPTH:
        next_stack: list[dict] = []
        for node in stack:
            errors = node.get("errors")
            if errors:
                found.extend(errors if isinstance(errors, list) else [errors])
            for key, value in node.items():
                if key == "errors":
                    continue
                if isinstance(value, dict):
                    next_stack.append(value)
        stack = next_stack
        depth += 1
    return found


def _plan(
    *,
    tool: str | None = None,
    arguments: dict | None = None,
    notes: str = "",
    blocked_reason: str | None = None,
    **extra: Any,
) -> dict:
    """Build a rollback record. Reversible only when a reverse call exists."""
    reversible = tool is not None and blocked_reason is None
    record: dict[str, Any] = {
        "reversible": reversible,
        "reverse_operation": tool if reversible else None,
        "reverse_call": (
            {"tool": tool, "arguments": arguments or {}} if reversible else None
        ),
        "notes": notes,
    }
    if blocked_reason is not None:
        record["blocked_reason"] = blocked_reason
    record.update(extra)
    return record


def _from_created(
    operation: str, result: Any, params: dict, *, delete_tool: str, id_arg: str
) -> dict:
    """Plan the undo of a create: delete whatever it made."""
    created_id = extract_entity_id(result)
    errors = payload_errors(result)

    if created_id is None:
        reason = (
            f"{operation} returned no entity ID"
            + (f"; the payload reported errors: {errors}" if errors else "")
            + ". Nothing was recorded to delete, so the create may not have "
            "taken effect. Check Monarch before retrying."
        )
        return _plan(
            notes="",
            blocked_reason=reason,
            creation_params=params,
            payload_errors=errors or None,
        )

    return _plan(
        tool=delete_tool,
        arguments={id_arg: created_id},
        notes=f"Deletes the {operation.removeprefix('create_')} that was created.",
        created_id=created_id,
        creation_params=params,
    )


def _changed_fields(params: dict, id_key: str) -> dict:
    """The fields an update actually set, ignoring the target's own ID."""
    return {
        key: value
        for key, value in params.items()
        if key != id_key and key != "confirmation_token" and value is not None
    }


def _from_pre_state_update(
    operation: str,
    params: dict,
    pre_state: dict | None,
    *,
    id_key: str,
    restore_tool: str,
) -> dict:
    """Plan the undo of an update: set the changed fields back."""
    target_id = params.get(id_key)
    changed = _changed_fields(params, id_key)

    if not pre_state:
        return _plan(
            blocked_reason=(
                f"No pre-operation snapshot was captured for {operation}, so the "
                "values it overwrote are not known. They cannot be recovered from "
                "this log."
            ),
            modified_id=target_id,
            modified_fields=changed,
        )

    prior = {key: pre_state.get(key) for key in changed if key in pre_state}
    missing = sorted(set(changed) - set(prior))
    if not prior:
        return _plan(
            blocked_reason=(
                f"The snapshot for {operation} held none of the fields it changed "
                f"({sorted(changed)}), so their prior values are unknown."
            ),
            modified_id=target_id,
            modified_fields=changed,
        )

    notes = "Restores the fields this operation overwrote to their prior values."
    if missing:
        notes += (
            f" Note: {missing} were changed but absent from the snapshot, so they "
            "are not restored by this call."
        )

    return _plan(
        tool=restore_tool,
        arguments={id_key: target_id, **prior},
        notes=notes,
        modified_id=target_id,
        modified_fields=changed,
        prior_values=prior,
    )


def _from_pre_state_delete(
    operation: str,
    params: dict,
    pre_state: dict | None,
    *,
    id_key: str,
    recreate_tool: str,
    recreate_args: dict | None,
    caveat: str,
) -> dict:
    """Plan the undo of a delete: recreate from the snapshot."""
    target_id = params.get(id_key)

    if not pre_state:
        return _plan(
            blocked_reason=(
                f"No pre-operation snapshot was captured for {operation}, so the "
                "deleted record's contents are not known. Recovery requires the "
                "Monarch web interface or an export taken before the delete."
            ),
            deleted_id=target_id,
        )

    if not recreate_args:
        return _plan(
            blocked_reason=(
                f"The snapshot for {operation} lacked the fields needed to "
                f"recreate the record: {sorted(pre_state)}."
            ),
            deleted_id=target_id,
            pre_state=pre_state,
        )

    return _plan(
        tool=recreate_tool,
        arguments=recreate_args,
        notes=(
            f"Recreates the deleted record from its pre-deletion snapshot. {caveat}"
        ),
        deleted_id=target_id,
        pre_state=pre_state,
    )


_NEW_ID_CAVEAT = (
    "The recreated record gets a new ID, so anything referencing the old ID "
    "will not be reconnected."
)


def build_rollback(
    operation: str,
    params: dict | None,
    result: Any = None,
    pre_state: dict | None = None,
) -> dict:
    """Build a rollback plan for one recorded operation.

    Args:
        operation: The operation name, e.g. ``delete_transaction``.
        params: Arguments the operation was called with.
        result: What the operation returned, used to find created IDs.
        pre_state: Snapshot taken before the operation ran, when one exists.

    Returns:
        A record whose ``reversible`` flag is true only when ``reverse_call``
        holds a complete, executable reverse call.
    """
    params = params or {}

    if operation == "create_transaction":
        return _from_created(
            operation,
            result,
            params,
            delete_tool="delete_transaction",
            id_arg="transaction_id",
        )

    if operation == "create_manual_account":
        return _from_created(
            operation,
            result,
            params,
            delete_tool="delete_account",
            id_arg="account_id",
        )

    if operation == "create_transaction_category":
        return _from_created(
            operation,
            result,
            params,
            delete_tool="delete_transaction_category",
            id_arg="category_id",
        )

    if operation == "create_tag":
        # Monarch's SDK exposes no delete-tag call, so this server cannot
        # undo it. Saying so beats implying an undo that does not exist.
        return _plan(
            blocked_reason=(
                "This server exposes no tool for deleting a tag. Remove it in "
                "the Monarch web interface if it was created by mistake."
            ),
            created_id=extract_entity_id(result),
            creation_params=params,
        )

    if operation == "delete_transaction":
        recreate_args = None
        if pre_state:
            required = ("account_id", "amount", "merchant_name", "category_id", "date")
            if all(pre_state.get(key) is not None for key in required):
                recreate_args = {key: pre_state[key] for key in required}
                if pre_state.get("notes"):
                    recreate_args["notes"] = pre_state["notes"]
        return _from_pre_state_delete(
            operation,
            params,
            pre_state,
            id_key="transaction_id",
            recreate_tool="create_transaction",
            recreate_args=recreate_args,
            caveat=_NEW_ID_CAVEAT,
        )

    if operation == "delete_account":
        recreate_args = None
        if pre_state and pre_state.get("name") and pre_state.get("account_type"):
            recreate_args = {
                "account_name": pre_state["name"],
                "account_type": pre_state["account_type"],
                "current_balance": pre_state.get("balance") or 0,
            }
            if pre_state.get("account_sub_type"):
                recreate_args["account_subtype"] = pre_state["account_sub_type"]
        return _from_pre_state_delete(
            operation,
            params,
            pre_state,
            id_key="account_id",
            recreate_tool="create_manual_account",
            recreate_args=recreate_args,
            caveat=(
                f"{_NEW_ID_CAVEAT} Only the account shell is restored — its "
                "transaction history and any linked-institution connection are "
                "not recoverable through this server."
            ),
        )

    if operation == "delete_transaction_category":
        recreate_args = None
        if pre_state and pre_state.get("name") and pre_state.get("group_id"):
            recreate_args = {
                "name": pre_state["name"],
                "group_id": pre_state["group_id"],
            }
            if pre_state.get("icon"):
                recreate_args["icon"] = pre_state["icon"]
        return _from_pre_state_delete(
            operation,
            params,
            pre_state,
            id_key="category_id",
            recreate_tool="create_transaction_category",
            recreate_args=recreate_args,
            caveat=(
                f"{_NEW_ID_CAVEAT} Transactions that used the old category are "
                "not reassigned to the new one."
            ),
        )

    if operation == "delete_transaction_categories":
        # A bulk delete needs one recreate per category, so there is no single
        # reverse call. The snapshot still carries what each one was.
        snapshots = (pre_state or {}).get("categories")
        if not snapshots:
            return _plan(
                blocked_reason=(
                    "No pre-operation snapshot was captured, so the deleted "
                    "categories' contents are not known."
                ),
                deleted_ids=_split_ids(params.get("category_ids")),
            )
        return _plan(
            blocked_reason=(
                "Bulk deletes have no single reverse call. Recreate each "
                "category from `pre_state.categories` with "
                "create_transaction_category."
            ),
            deleted_ids=_split_ids(params.get("category_ids")),
            pre_state=pre_state,
        )

    if operation == "update_transaction":
        return _from_pre_state_update(
            operation,
            params,
            pre_state,
            id_key="transaction_id",
            restore_tool="update_transaction",
        )

    if operation == "update_account":
        return _from_pre_state_update(
            operation,
            params,
            pre_state,
            id_key="account_id",
            restore_tool="update_account",
        )

    if operation == "categorize_transaction":
        prior_category = (pre_state or {}).get("category_id")
        if prior_category is None:
            return _plan(
                blocked_reason=(
                    "No snapshot of the transaction's previous category was "
                    "captured, so it is not known."
                ),
                modified_id=params.get("transaction_id"),
                new_category_id=params.get("category_id"),
            )
        return _plan(
            tool="categorize_transaction",
            arguments={
                "transaction_id": params.get("transaction_id"),
                "category_id": prior_category,
            },
            notes="Restores the transaction's previous category.",
            modified_id=params.get("transaction_id"),
            new_category_id=params.get("category_id"),
            prior_values={"category_id": prior_category},
        )

    if operation in ("add_transaction_tag", "set_transaction_tags"):
        prior_tags = (pre_state or {}).get("tag_ids")
        if prior_tags is None:
            return _plan(
                blocked_reason=(
                    "No snapshot of the transaction's previous tags was "
                    "captured, so the original tag list is not known."
                ),
                modified_id=params.get("transaction_id"),
            )
        return _plan(
            tool="set_transaction_tags",
            arguments={
                "transaction_id": params.get("transaction_id"),
                "tag_ids": ",".join(prior_tags) if prior_tags else "",
            },
            notes="Restores the transaction's previous tag list.",
            modified_id=params.get("transaction_id"),
            prior_values={"tag_ids": prior_tags},
        )

    if operation == "set_budget_amount":
        prior_amount = (pre_state or {}).get("amount")
        if prior_amount is None:
            return _plan(
                blocked_reason=(
                    "No snapshot of the previous budget amount was captured."
                ),
                modified_fields=_changed_fields(params, "category_id"),
            )
        # Carry through everything that identifies *which* budget was set, so
        # the restore targets the same category and period as the original.
        restore = {
            key: params.get(key)
            for key in (
                "category_id",
                "category_group_id",
                "timeframe",
                "start_date",
            )
            if params.get(key) is not None
        }
        return _plan(
            tool="set_budget_amount",
            arguments={**restore, "amount": prior_amount},
            notes="Restores the previous budget amount.",
            prior_values={"amount": prior_amount},
        )

    if operation == "update_transaction_splits":
        prior_splits = (pre_state or {}).get("splits")
        if prior_splits is None:
            return _plan(
                blocked_reason=(
                    "No snapshot of the transaction's previous splits was captured."
                ),
                modified_id=params.get("transaction_id"),
            )
        return _plan(
            tool="update_transaction_splits",
            arguments={
                "transaction_id": params.get("transaction_id"),
                "splits_data": json.dumps(prior_splits),
            },
            notes="Restores the transaction's previous splits.",
            modified_id=params.get("transaction_id"),
            prior_values={"splits": prior_splits},
        )

    if operation == "upload_account_balance_history":
        return _plan(
            blocked_reason=(
                "Uploaded balance history overwrites existing snapshots in "
                "bulk and has no inverse operation. Restoring it requires a "
                "Monarch export taken before the upload."
            ),
            account_id=params.get("account_id"),
        )

    if operation == "upload_attachment":
        return _plan(
            blocked_reason=(
                "This server exposes no tool for removing an attachment. "
                "Delete it in the Monarch web interface."
            ),
            modified_id=params.get("transaction_id"),
        )

    return _plan(
        blocked_reason=f"No rollback plan is defined for {operation}.",
    )


def _split_ids(raw: Any) -> list[str]:
    """Split a comma-separated ID string into a list."""
    if not isinstance(raw, str):
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]
