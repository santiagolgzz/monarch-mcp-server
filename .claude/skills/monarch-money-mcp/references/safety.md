# Safety System Details

## Three-Tier Protection

### Tier 1: Destructive Operations
**Require user approval before execution.**

Operations:
- `delete_transaction`
- `delete_account`
- `delete_transaction_category`
- `delete_transaction_categories`
- `upload_account_balance_history`

Example flow:
```
User: "Delete transaction ABC123"
Claude: ⚠️ About to execute: delete_transaction(transaction_id="ABC123")
        [Approve] [Deny]
```

### Tier 2: Write Operations
**Show warning, don't require approval.**

Operations:
- `create_transaction`
- `update_transaction`
- `create_manual_account`
- `update_account`
- `set_budget_amount`

### Tier 3: Read Operations
**No protection needed.**

All `get_*` tools are completely safe.

## Emergency Controls

```python
# Immediately block ALL write operations
enable_emergency_stop()

# Resume normal operation
disable_emergency_stop()
```

## Audit Log Location
- Summary: `~/.mm/operation_log.json`
- Detailed: `~/.mm/detailed_operation_log.jsonl`

## Rollback

```python
# View recent operations
get_recent_operations(limit=10)

# Get undo instructions
get_rollback_suggestions(operation_index=0)
```
