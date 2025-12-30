---
name: monarch-money-mcp
description: "Use for viewing financial accounts, transactions, budgets, and cashflow from Monarch Money. Use for creating or updating transactions. Triggers: finances, spending, accounts, budgets"
---

# Monarch Money MCP

Access ~40 tools for Monarch Money personal finance. See [tools.md](references/tools.md) for full list.

## Quick Start

```
get_accounts              # List all accounts
get_transactions          # Recent transactions
get_budgets               # Budget vs actual
get_cashflow              # Income vs expenses
```

## Safety (CRITICAL)

- **Read-only tools are safe** - All `get_*` tools
- **Destructive ops require approval** - `delete_*` tools prompt user first
- **Emergency stop** - `enable_emergency_stop` blocks all writes
- **Dates** - Always YYYY-MM-DD format

See [safety.md](references/safety.md) for tiers.

## Common Tools

| Tool | Use |
|------|-----|
| `get_accounts` | Account balances |
| `get_transactions` | Query with `limit`, `start_date`, `end_date` |
| `get_recurring_transactions` | Subscriptions |
| `create_transaction` | Add manual entry |
| `delete_transaction` | ⚠️ Requires approval |

## Auth Error

If auth fails → User must run `python login_setup.py`
