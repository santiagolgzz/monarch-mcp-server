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

### Scenario 1: Accidentally Deleted a Transaction

**What Happened:**
You approved deletion of transaction without realizing which one it was.

**How to Rollback:**

1. **Check what was deleted:**
   ```bash
   get_recent_operations(limit=5)
   ```

2. **Get rollback instructions:**
   ```bash
   get_rollback_suggestions(operation_index=0)
   ```
   Shows the deleted transaction ID.

3. **Get original transaction details:**
   - Check Monarch Money web interface for transaction history
   - Or if you had exported data beforehand, use that

4. **Recreate the transaction:**
   ```bash
   create_transaction(
       account_id="account_xyz",
       amount=-50.00,
       description="Groceries at Safeway",
       date="2025-01-28",
       category_id="category_groceries"
   )
   ```

**Prevention:**
Always check `get_transaction_details(transaction_id)` BEFORE deleting to save the details.

### Scenario 2: Created Transaction by Mistake

**What Happened:**
Created a transaction with wrong data or duplicate.

**How to Rollback:**

1. **View recent operations:**
   ```bash
   get_recent_operations()
   ```

2. **Get the created ID:**
   ```bash
   get_rollback_suggestions(operation_index=0)
   ```
   Shows: "Created ID: txn_new123"

3. **Delete it:**
   ```bash
   delete_transaction(transaction_id="txn_new123")
   ```

**Easy!** Created items can be deleted immediately using their ID from the log.

### Scenario 3: Updated Transaction Incorrectly

**What Happened:**
Changed transaction amount or category to wrong value.

**How to Rollback:**

1. **Check what changed:**
   ```bash
   get_rollback_suggestions(operation_index=0)
   ```
   Shows:
   ```
   Modified ID: txn_abc123
   Changed fields: amount, category_id
   Note: You need the original values to restore
   ```

2. **Get original values:**
   - **Best**: You kept notes before updating
   - **Good**: Check Monarch Money web interface history
   - **Okay**: Estimate from memory

3. **Update back:**
   ```bash
   update_transaction(
       transaction_id="txn_abc123",
       amount=-75.00,  # Original amount
       category_id="cat_original"  # Original category
   )
   ```

**Prevention:**
Use `get_transaction_details(transaction_id)` BEFORE updating and save the output.

### Scenario 4: Deleted Multiple Categories

**What Happened:**
Used `delete_transaction_categories` and deleted too many.

**How to Rollback:**

1. **Check what was deleted:**
   ```bash
   get_rollback_suggestions(operation_index=0)
   ```
   Shows all deleted category IDs.

2. **Get original category details:**
   - If you ran `get_transaction_categories()` before deleting, use that output
   - Otherwise, check Monarch Money web interface

3. **Recreate each category:**
   ```bash
   create_transaction_category(name="Original Name 1", group_id="group_id")
   create_transaction_category(name="Original Name 2", group_id="group_id")
   # ... for each deleted category
   ```

**Prevention:**
Run `get_transaction_categories()` and save output BEFORE bulk deleting.

### Scenario 5: Runaway Claude Created 50 Transactions

**What Happened:**
Claude went rogue and created many unwanted transactions before you stopped it.

**How to Rollback:**

1. **Stop further damage:**
   ```bash
   enable_emergency_stop
   ```

2. **Review all recent operations:**
   ```bash
   get_recent_operations(limit=50)
   ```

3. **Identify the unwanted transactions:**
   Look through the list for the runaway creates.

4. **Delete each unwanted transaction:**
   ```bash
   # For each unwanted transaction in the log:
   delete_transaction(transaction_id="txn_001")
   delete_transaction(transaction_id="txn_002")
   # ... etc
   ```

5. **Re-enable when done:**
   ```bash
   disable_emergency_stop
   ```

**Tip:** Created operations show their `created_id` in rollback info - use that to delete.

## Best Practices

### Before Destructive Operations

1. **Save current state:**
   ```bash
   # Before deleting transaction
   get_transaction_details(transaction_id="txn_123")
   # Save the output!

   # Before deleting account
   get_accounts()  # Find and save account details

   # Before bulk category delete
   get_transaction_categories()  # Save all categories
   ```

2. **Test small first:**
   - Delete 1 transaction, verify it worked
   - Then delete the rest if needed

3. **Use specific queries:**
   - Don't delete based on vague criteria
   - Get exact IDs first, then delete

### After Operations

1. **Review immediately:**
   ```bash
   get_recent_operations(limit=5)
   ```
   Check that what you did matches what you intended.

2. **Keep log file:**
   - Don't delete `~/.mm/detailed_operation_log.jsonl`
   - It's your insurance policy

3. **Regular backups:**
   - Periodically run `get_transactions(limit=1000)` and save
   - Export from Monarch Money web interface

## Limitations

### What CAN Be Rolled Back

| Operation | Reversibility | Method |
|-----------|--------------|---------|
| **create_transaction** | ✅ Easy | Delete using created ID |
| **create_manual_account** | ✅ Easy | Delete using created ID |
| **create_transaction_category** | ✅ Easy | Delete using created ID |
| **create_tag** | ✅ Easy | Delete using created ID |
| **delete_transaction** | ⚠️  Requires original data | Recreate using saved details |
| **delete_account** | ⚠️  Requires original data | Recreate using saved details |
| **delete_transaction_category** | ⚠️  Requires original data | Recreate using saved details |
| **update_transaction** | ⚠️  Requires original values | Update back using saved values |
| **update_account** | ⚠️  Requires original values | Update back using saved values |

### What CANNOT Be Easily Rolled Back

- **Deletions without saved data**: If you didn't save transaction/account/category details before deleting, rollback requires manual work
- **Updates without original values**: If you didn't note original values, you can't restore them exactly
- **Monarch Money web changes**: Changes made outside this MCP server aren't logged

### Workarounds

1. **For deletions**: Always use Monarch Money's web interface to view history
2. **For updates**: Keep a notebook of original values before changing
3. **For everything**: Regular backups via Monarch Money web export

## Tips

### Make Rollback Easy

1. **Create pre-operation snapshots:**
   ```bash
   # Before big changes
   get_accounts() > accounts_backup.json
   get_transactions(limit=1000) > transactions_backup.json
   get_transaction_categories() > categories_backup.json
   ```

2. **Use descriptive operations:**
   Instead of bulk deletes, delete one at a time with approval.
   Easier to rollback if something goes wrong.

3. **Test in Monarch Money sandbox:**
   If Monarch Money offers a test environment, use it first.

### Regular Maintenance

1. **Review logs weekly:**
   ```bash
   get_recent_operations(limit=20)
   ```

2. **Clean old logs:**
   The detailed log grows over time. Archive or delete entries older than 30 days if needed.

3. **Backup the log:**
   ```bash
   cp ~/.mm/detailed_operation_log.jsonl ~/.mm/backups/detailed_operation_log_$(date +%Y%m%d).jsonl
   ```

## Summary

✅ **Every write operation is logged** with full details
✅ **View recent operations** with `get_recent_operations()`
✅ **Get rollback instructions** with `get_rollback_suggestions()`
✅ **Created items** → Easy to delete using logged ID
⚠️  **Deleted items** → Need original data to recreate
⚠️  **Updated items** → Need original values to restore

**Best practice:** Save current state before destructive operations!
