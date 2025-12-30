# Safety Features - Monarch Money MCP Server Extended

## Overview

This extended version uses **user approval prompts** (like Claude Code commands) to prevent runaway operations, providing better protection than rate limits while maintaining usability.

## How Safety Works

### User Approval System

Destructive operations require your explicit approval before executing:

```
You: Delete transaction ABC123
Claude: ⚠️  About to execute: delete_transaction(transaction_id="ABC123")
        This is a DESTRUCTIVE operation that will permanently remove this transaction.

        [Approve] [Deny]
```

You must click **[Approve]** for the operation to proceed. This prevents:
- Runaway Claude instances from deleting your data
- Accidental bulk operations
- Unintended destructive changes

### Three-Tier Protection

#### Tier 1: Destructive Operations (REQUIRE APPROVAL)

These operations **always** prompt for user approval:

- `delete_transaction` - Delete transactions
- `delete_account` - Delete accounts
- `delete_transaction_category` - Delete categories
- `delete_transaction_categories` - Bulk delete categories
- `upload_account_balance_history` - Upload CSV data (can overwrite history)

**Example:**
```
You: Delete all transactions in the "Test" category
Claude: I'll need to:
        1. Find transactions in "Test" category
        2. Delete each one (requires approval per transaction)

        Found 5 transactions. Delete transaction TXN_001?
        [Approve] [Deny]
```

#### Tier 2: Write Operations (WARNING ONLY)

These operations show warnings but don't require approval:

- `create_transaction` - Create new transactions
- `update_transaction` - Modify transactions
- `create_manual_account` - Create accounts
- `update_account` - Modify accounts
- `set_budget_amount` - Update budgets

**Example:**
```
You: Create a transaction for $50 groceries
Claude: ℹ️ Creating transaction...
        [Transaction created successfully]
```

#### Tier 3: Read Operations (NO PROTECTION)

Read-only operations never require approval:
- `get_accounts`, `get_transactions`, `get_budgets`, etc.

### Emergency Stop

Manual kill switch to block **ALL** write operations:

```bash
# Immediately disable all writes
enable_emergency_stop

# Re-enable when safe
disable_emergency_stop
```

When emergency stop is active:
- ✅ All read operations work normally
- ❌ All write operations are blocked (even with approval)
- Useful if you suspect runaway behavior

## Safety Tools

### Monitor Activity

```
# View today's operation statistics
get_safety_stats

# Returns:
# {
#   "date": "2025-01-29",
#   "operations_today": {
#     "create_transaction": 15,
#     "delete_transaction": 3
#   },
#   "total_operations_today": 18,
#   "emergency_stop": false,
#   "approval_required_for": ["delete_transaction", "delete_account", ...]
# }
```

### Emergency Controls

```

### Operation Log Sensitivity

Write operations are logged to `~/.mm/detailed_operation_log.jsonl` to enable rollback guidance.
These entries may include sensitive data (transaction descriptions, amounts, IDs, and category
names). If you operate on a shared machine, consider:

- Restricting access to your home directory
- Rotating or deleting the log periodically
- Disabling safety logging by setting `"enabled": false` in `~/.mm/safety_config.json` (not recommended)
# Stop everything NOW
enable_emergency_stop

# Resume normal operation
disable_emergency_stop
```

## Configuration

### Default Configuration

Located at `~/.mm/safety_config.json` (auto-created):

```json
{
  "require_approval": [
    "delete_transaction",
    "delete_account",
    "delete_transaction_category",
    "delete_transaction_categories",
    "upload_account_balance_history"
  ],
  "warn_before_execute": [
    "create_transaction",
    "update_transaction",
    "create_manual_account",
    "update_account",
    "set_budget_amount"
  ],
  "emergency_stop": false,
  "enabled": true
}
```

### Customize Approval Requirements

Edit `~/.mm/safety_config.json`:

```json
{
  "require_approval": [
    "delete_transaction",
    "delete_account",
    "create_transaction"  // Add: now requires approval
  ],
  "warn_before_execute": [
    "update_transaction"  // Remove others for less warnings
  ]
}
```

### Disable Safety (NOT RECOMMENDED)

```json
{
  "enabled": false  // ⚠️  Removes all protection
}
```

## Runaway Protection Scenarios

### Scenario 1: Bulk Deletion Attempt

```
You: Delete all my test transactions
Claude: Found 50 transactions to delete.

        Delete transaction #1 (Test Payment $10)?
        [Approve] [Deny]

You: [Deny]  ← User stops the runaway operation
```

**Protection**: Each deletion requires individual approval. If Claude goes rogue and tries to delete 1000 transactions, you'll see the first prompt and can stop it.

### Scenario 2: Runaway Account Creation

```
Claude (glitching): Creating account "Test"...
Claude (glitching): Creating account "Test"...
Claude (glitching): Creating account "Test"...
```

**Result**: 3 accounts created with warnings logged. No approval required for creates, but audit log shows unusual activity. Use `get_safety_stats` to detect.

**Response**: Use `enable_emergency_stop` to block further operations.

### Scenario 3: Mass Category Deletion

```
You: Clean up my categories
Claude (misunderstanding): I'll delete unused categories.

        Delete category "Groceries"?
        [Approve] [Deny]

You: [Deny] ← That's not unused!
```

**Protection**: Approval prompt reveals Claude's misunderstanding before damage occurs.

### Scenario 4: Emergency Stop Active

```
# Emergency stop enabled
You: Delete transaction ABC123
Claude: 🚨 EMERGENCY STOP ACTIVE: All write operations disabled.
        Use disable_emergency_stop() to re-enable.
```

**Protection**: Even with approval, operation cannot execute during emergency stop.

## Operation Audit Log

### Summary Log

Daily operation counts stored in `~/.mm/operation_log.json`:

```json
{
  "2025-01-29": {
    "counts": {
      "create_transaction": 15,
      "update_transaction": 8,
      "delete_transaction": 2,
      "delete_account": 1
    },
    "last_updated": "2025-01-29T14:30:00"
  }
}
```

### Detailed Rollback Log (NEW!)

Every write operation is logged with complete details in `~/.mm/detailed_operation_log.jsonl`:

```json
{
  "timestamp": "2025-01-29T14:30:15.123456",
  "operation": "delete_transaction",
  "parameters": {
    "transaction_id": "txn_abc123"
  },
  "result_preview": "{\"success\": true, \"deleted\": true}",
  "rollback_info": {
    "reversible": true,
    "reverse_operation": "create_transaction",
    "notes": "To recreate: Use transaction details from get_transaction_details(txn_abc123)",
    "deleted_id": "txn_abc123"
  }
}
```

**Rollback information includes:**
- **For deletions**: ID of deleted item, instructions to recreate
- **For creations**: ID of created item (for easy deletion)
- **For updates**: Modified fields and IDs (original values needed from backup)
- **Reversibility**: Whether operation can be easily undone

**Use cases:**
- Detect unusual activity patterns
- Audit what operations were performed
- Track usage over time
- **Rollback unwanted operations**
- Investigate if something went wrong

## Rollback Guide

### View Recent Operations

```bash
# See last 10 operations with rollback info
get_recent_operations()

# See last 20 operations
get_recent_operations(limit=20)
```

### Get Rollback Instructions

```bash
# Get rollback suggestions for most recent operation
get_rollback_suggestions(operation_index=0)

# Get suggestions for 2nd most recent
get_rollback_suggestions(operation_index=1)
```

**Example Output:**
```
🔄 Rollback Information for Operation #5

📅 Timestamp: 2025-01-29T14:30:15
⚙️  Operation: delete_transaction
📝 Parameters: {"transaction_id": "txn_123"}

✅ REVERSIBLE

🔄 Reverse Operation: create_transaction
📋 Instructions: To recreate: Use transaction details from get_transaction_details(txn_123)

💡 To undo: Recreate the deleted item using its original details
   Deleted ID: txn_123
```

### Common Rollback Scenarios

**Accidentally Deleted Transaction:**
```bash
1. get_recent_operations(limit=5)
2. get_rollback_suggestions(operation_index=0)
3. Recreate using original details from Monarch Money web interface
```

**Created Wrong Transaction:**
```bash
1. get_recent_operations()
2. get_rollback_suggestions(operation_index=0)
   # Shows: "Created ID: txn_xyz456"
3. delete_transaction(transaction_id="txn_xyz456")
```

**Bulk Operation Went Wrong:**
```bash
1. enable_emergency_stop  # Stop further damage
2. get_recent_operations(limit=50)  # Review all recent ops
3. get_rollback_suggestions for each unwanted operation
4. Undo operations one by one
5. disable_emergency_stop  # Resume when safe
```

## Best Practices

### For Regular Use

1. ✅ **Approve carefully** - Read each approval prompt before clicking
2. ✅ **Check stats periodically** - `get_safety_stats` to monitor activity
3. ✅ **Review audit log** - Check `~/.mm/operation_log.json` monthly
4. ✅ **Use emergency stop** - When in doubt, stop everything

### For Bulk Operations

1. ✅ **Test small first** - "Delete 3 test transactions" before "Delete all test transactions"
2. ✅ **Review plan** - Ask Claude to explain what it will do before approving
3. ✅ **Approve individually** - Don't spam-click approve without reading
4. ✅ **Have backup** - Know you can deny mid-operation

### Red Flags

🚨 **Stop and investigate if you see:**
- Approval prompts you didn't expect
- Rapid succession of approval requests
- Operations on wrong accounts/categories
- Bulk operations you didn't request
- Unusual operation counts in `get_safety_stats`

**Action**: Click **[Deny]** or use `enable_emergency_stop`

## Comparison: Approval vs Rate Limits

| Feature | User Approval ✅ | Rate Limits ❌ |
|---------|------------------|----------------|
| **Prevents unwanted ops** | Yes - requires explicit approval | No - just slows them down |
| **User control** | Full control per operation | No control, just artificial delays |
| **Usability** | Great - approve legitimate ops instantly | Poor - forced to wait even for good ops |
| **Protection** | Perfect - runaway can't do anything | Partial - runaway still does some damage |
| **Bulk operations** | Works fine - approve what you want | Painful - hit limits during legit work |
| **False positives** | Zero - you decide each time | High - limits affect everyone |

## FAQ

**Q: Do I need to approve every transaction I create?**
A: No, only deletions require approval. Creates just show warnings.

**Q: What if I accidentally approve a deletion?**
A: Check your Monarch Money web interface and use their undo features if available, or manually recreate the item.

**Q: Can I disable approvals for specific operations?**
A: Yes, edit `~/.mm/safety_config.json` and remove operations from `require_approval` list.

**Q: Will approval prompts slow me down?**
A: Only for destructive operations, which you'd want to confirm anyway. Creates and updates don't require approval.

**Q: What happens if Claude tries 1000 deletions?**
A: You'll see the first approval prompt, deny it, and use `enable_emergency_stop`.

**Q: Does this work like Claude Code's command approval?**
A: Yes, same mechanism - MCP tools requiring approval prompt the user in Claude Desktop.

**Q: Can a runaway Claude bypass the approval?**
A: No, Claude cannot approve its own operations. Only you can click [Approve].

## Technical Details

### Implementation

- **Decorator-based**: Clean separation via `@require_safety_check()`
- **MCP-native**: Uses Claude Desktop's built-in approval system
- **Audit logging**: All operations logged to `~/.mm/operation_log.json`
- **Configurable**: Customize which operations require approval
- **Emergency stop**: Nuclear option to block all writes

### Files

- `src/monarch_mcp_server/safety.py` - Safety module (~200 lines)
- `~/.mm/safety_config.json` - User configuration
- `~/.mm/operation_log.json` - Operation audit trail

## Summary

**User approval** is the right way to prevent runaway operations:

1. ✅ **Explicit control** - You approve each destructive operation
2. ✅ **No false positives** - Legitimate bulk ops work fine
3. ✅ **Audit trail** - All operations logged
4. ✅ **Emergency stop** - Kill switch for total lockdown
5. ✅ **Configurable** - Customize approval requirements

**Your financial data is protected by your explicit approval.** 🛡️

No runaway Claude can delete your accounts, transactions, or categories without you clicking [Approve] for each one.
