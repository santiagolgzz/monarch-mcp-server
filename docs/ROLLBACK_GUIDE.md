# Rollback Guide - Monarch Money MCP Server

## Overview

Every write operation is logged with complete details, allowing you to review and potentially rollback unwanted changes.

## How It Works

### Automatic Logging

Every time you perform a write operation (create, update, delete), the system logs:
- **Timestamp**: When the operation occurred
- **Operation Type**: What was done (e.g., delete_transaction)
- **Parameters**: All details passed to the operation
- **Result**: First 500 characters of the result
- **Rollback Info**: Instructions and data needed to undo

### Log Location

`~/.mm/detailed_operation_log.jsonl` (JSON Lines format - one JSON object per line)

## Available Tools

### 1. View Recent Operations

```bash
get_recent_operations(limit=10)
```

**Returns:**
- List of recent write operations
- Full parameters used
- Rollback information for each
- Timestamp of when it occurred

**Example:**
```json
{
  "count": 3,
  "operations": [
    {
      "timestamp": "2025-01-29T14:30:15.123456",
      "operation": "delete_transaction",
      "parameters": {
        "transaction_id": "txn_abc123"
      },
      "rollback_info": {
        "reversible": true,
        "reverse_operation": "create_transaction",
        "deleted_id": "txn_abc123",
        "notes": "To recreate: Use transaction details..."
      }
    }
  ]
}
```

### 2. Get Rollback Suggestions

```bash
get_rollback_suggestions(operation_index=0)  # 0 = most recent
get_rollback_suggestions(operation_index=1)  # 1 = second most recent
```

**Returns:**
Detailed, human-readable instructions on how to undo the operation.

**Example Output:**
```
🔄 Rollback Information for Operation #147

📅 Timestamp: 2025-01-29T14:30:15
⚙️  Operation: delete_transaction
📝 Parameters: {
  "transaction_id": "txn_abc123"
}

✅ REVERSIBLE

🔄 Reverse Operation: create_transaction
📋 Instructions: To recreate: Use transaction details from get_transaction_details(txn_abc123)

💡 To undo: Recreate the deleted item using its original details
   Deleted ID: txn_abc123
```

## Rollback Scenarios

The short version: run `get_rollback_suggestions(operation_index=0)` and it
prints the exact call that undoes the most recent write, or tells you why it
cannot.

### Scenario 1: Accidentally deleted a transaction

```bash
get_rollback_suggestions(operation_index=0)
```

```
REVERSIBLE

Recreates the deleted record from its pre-deletion snapshot. The recreated
record gets a new ID, so anything referencing the old ID will not be
reconnected.

Run this to undo it:

  create_transaction(account_id='acc_1', amount=-42.5,
                     merchant_name='Cafe Example', category_id='cat_food',
                     date='2026-03-04', notes='lunch')
```

Run that call. The values come from the snapshot taken before the delete, so
you do not need to have saved anything yourself.

### Scenario 2: Created a transaction by mistake

```
REVERSIBLE

Deletes the transaction that was created.

Run this to undo it:

  delete_transaction(transaction_id='txn_created_1')
```

### Scenario 3: Updated a transaction incorrectly

The reverse call restores **only** the fields the update changed, using the
values they held beforehand. Fields you did not touch are left alone. If a
changed field was missing from the snapshot, the notes say which, so you know
what the reverse call will not cover.

### Scenario 4: Deleted multiple categories

Bulk deletes have no single reverse call. The entry reports this and carries a
`pre_state.categories` list; recreate each one with
`create_transaction_category`.

### Scenario 5: Runaway agent made many changes

1. `enable_emergency_stop` — refuses all further writes immediately.
2. `get_recent_operations(limit=50)` — every entry carries its own
   `rollback_info.reverse_call`.
3. Run the reverse calls in **reverse chronological order**, so later changes
   are undone before the earlier ones they were layered on.
4. `disable_emergency_stop` when finished.

Two things now stop this before it gets far: destructive calls are refused
until confirmed, and each operation has a daily cap. See the README's safety
section for both.

## Limitations

### Reversible from the log

| Operation | Reversible when |
|-----------|-----------------|
| `create_transaction` | Always — the new ID is recorded |
| `create_manual_account` | Always — the new ID is recorded |
| `create_transaction_category` | Always — the new ID is recorded |
| `delete_transaction` | A snapshot was captured |
| `delete_account` | A snapshot was captured (shell only, see below) |
| `delete_transaction_category` | A snapshot was captured |
| `update_transaction` / `update_account` | A snapshot holds the changed fields |
| `categorize_transaction` | A snapshot holds the prior category |
| `add_transaction_tag` / `set_transaction_tags` | A snapshot holds the prior tag list |
| `set_budget_amount` | A snapshot holds the prior amount |
| `update_transaction_splits` | A snapshot holds the prior splits |

### Not reversible through this server

| Operation | Why |
|-----------|-----|
| `create_tag` | No delete-tag tool exists — remove it in the web interface |
| `upload_attachment` | No remove-attachment tool exists |
| `upload_account_balance_history` | Bulk overwrite with no inverse; needs a pre-upload export |
| `delete_transaction_categories` | Recoverable, but as one recreate per category rather than a single call |

### Caveats that apply to every recreate

- **New IDs.** A recreated record is a new record. Anything that referenced the
  old ID — splits, rules, links — is not reconnected.
- **Deleted accounts lose history.** Only the account shell is restored. Its
  transactions and any linked-institution connection are not recoverable here.
- **Deleted categories do not reclaim their transactions.** Transactions
  reassigned by the delete stay where they went.
- **Changes made in the Monarch web interface are not logged**, so they cannot
  be rolled back from here.

### When a snapshot is missing

Snapshot capture is best-effort: if the read fails (network, or the record was
already gone), the operation still proceeds and the entry records
`pre_state_error`. Those operations report as not reversible, with the reason
stated. Recovery then needs the Monarch web interface or an export.

## Tips

### Before destructive operations

Snapshots are captured automatically, so keeping your own notes is no longer
required. Two things still help:

1. **Check what you are about to act on.** `get_transaction_details(id)` or
   `get_accounts()` confirms you have the right record.
2. **Prefer one-at-a-time over bulk.** Bulk deletes are the one case with no
   single reverse call.

### Maintenance

1. **Review recent activity:**
   ```bash
   get_recent_operations(limit=20)
   ```

2. **Archive old entries.** The detailed log grows with every write and now
   carries snapshots, so it grows faster than before. Archive it periodically:
   ```bash
   cp ~/.mm/detailed_operation_log.jsonl \
      ~/.mm/backups/detailed_operation_log_$(date +%Y%m%d).jsonl
   ```

   Snapshots are what make deletes reversible, so archive rather than delete if
   you may still need to undo something.

## Summary

- **Every write is logged**, successes and failures alike.
- **Destructive and update operations capture a snapshot first**, which is what
  makes them reversible.
- **`get_rollback_suggestions` prints a runnable reverse call** — or names
  exactly what is missing, and never claims an undo it cannot back up.
- **Creates** reverse to a delete using the recorded ID.
- **Recreated records get new IDs**; deleted accounts do not regain their
  transaction history.
