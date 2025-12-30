---
name: monarch-money-mcp
description: "Use for managing Monarch Money finances: accounts, transactions, budgets, and cashflow. Triggers: finances, spending, accounts, budgets"
---

# Monarch Money MCP

Access ~40 tools for Monarch Money personal finance.
- **[tools.md](references/tools.md)**: Full tool list
- **[safety.md](references/safety.md)**: Safety tiers
- **[financial-analysis.md](references/financial-analysis.md)**: Analysis guides

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
