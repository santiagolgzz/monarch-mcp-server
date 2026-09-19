# Safety System Details

## Three-Tier Protection

### Tier 1: Destructive Operations
**Withheld until confirmed with a token.**

Operations:
- `delete_transaction`
- `delete_account`
- `delete_transaction_category`
- `delete_transaction_categories`
- `upload_account_balance_history`

Each takes a `confirmation_token` parameter. The first call is refused and
returns a challenge; repeating the identical call with that token carries the
operation out. The token is single-use, bound to those exact arguments, and
expires after `confirmation_ttl_seconds` (300 by default).

```
delete_transaction(transaction_id="txn_1")
→ {"error": "Confirmation required",
   "about_to_change": "Transaction 'Cafe Example' for -42.5 on 2026-03-04",
   "confirmation_token": "8Kq...", "expires_in_seconds": 300}

delete_transaction(transaction_id="txn_1", confirmation_token="8Kq...")
→ {"deleted": true, "transaction_id": "txn_1"}
```

Show `about_to_change` to the user before confirming — that is the point of the
two steps. Setting `require_confirmation: false` in `~/.mm/safety_config.json`
restores warn-and-proceed.

### Tier 2: Write Operations
**Show warning, don't require approval.**

Operations:
- `create_transaction`
- `update_transaction`
- `update_transaction_splits`
- `create_manual_account`
- `update_account`
- `set_budget_amount`
- `add_transaction_tag`
- `categorize_transaction`
- `upload_attachment`

### Tier 2b: Recorded-Only Write Operations
**No warning, but recorded in audit log.**

Operations:
- `create_tag`
- `set_transaction_tags`
- `create_transaction_category`

### Tier 3: Read Operations
**No protection needed.**

All `get_*`, `search_*`, and `is_*` tools are completely safe.

## Daily Caps

Each operation has a per-day ceiling on **successful** writes, set under
`daily_limits` in `~/.mm/safety_config.json`. Exceeding one refuses the call
and names the setting to raise. Failures do not count, so a flapping upstream
cannot exhaust the day's allowance. `null` means no limit.

Defaults: `delete_transaction` 50, `delete_account` 5,
`delete_transaction_category` 25, `delete_transaction_categories` 5,
`upload_account_balance_history` 10, `create_transaction` 200,
`update_transaction` 200.

## Emergency Controls

```python
# Immediately block ALL write operations
enable_emergency_stop()

# Resume normal operation
disable_emergency_stop()
```

## Audit & Rollback

```python
# Check operation counts and e-stop status
get_safety_stats()

# View recent write operations with details
get_recent_operations(limit=10)

# Get undo instructions for a specific operation
get_rollback_suggestions(operation_index=0)
```

## Rollback

`get_rollback_suggestions(operation_index=0)` prints the exact call that
reverses an operation, built from a snapshot captured before the write ran:

```
REVERSIBLE

Run this to undo it:

  create_transaction(account_id='acc_1', amount=-42.5,
                     merchant_name='Cafe Example', category_id='cat_food',
                     date='2026-03-04')
```

When the data needed to reverse it was not captured, it says so and names what
is missing rather than implying an undo that would not work. Recreated records
get new IDs; a deleted account's transaction history is not restored.

## Audit Log Location
- Summary: `~/.mm/operation_log.json`
- Detailed: `~/.mm/detailed_operation_log.jsonl`

## Tool Annotations

Every tool declares MCP annotations, so a client can gate destructive calls on
its own without knowing anything about this server:

| Hint | Meaning here |
|------|--------------|
| `readOnlyHint` | True for all `get_*`, `search_*`, `is_*`, `check_*` |
| `destructiveHint` | True for exactly the Tier 1 operations below |
| `idempotentHint` | False for creates and `upload_attachment`; true otherwise |
| `openWorldHint` | False — every tool acts on one account on one service |

A client that prompts on `destructiveHint` will prompt before the same five
operations this server withholds.

## Source of Truth

These tiers are the defaults in `SafetyConfig._load_config`
(`src/monarch_mcp_server/safety_config.py`). Users can override them in
`~/.mm/safety_config.json`, so a specific install may differ.

`tests/test_skill_accuracy.py` checks the Tier 1 / Tier 2 lists above against
those defaults, so this file cannot drift out of sync with the code.
