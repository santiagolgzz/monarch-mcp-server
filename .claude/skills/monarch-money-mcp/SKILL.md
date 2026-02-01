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
get_accounts                  # List all accounts
get_transactions              # Recent transactions
get_transaction_categories    # Get category IDs (needed for create)
get_budgets                   # Budget vs actual
get_cashflow                  # Income vs expenses
```

## Safety (CRITICAL)

- **Read-only tools are safe** - All `get_*` tools
- **Destructive ops require approval** - `delete_*` tools prompt user first
- **Emergency stop** - `enable_emergency_stop` blocks all writes
- **Dates** - Always YYYY-MM-DD format

## Common Tools

| Tool | Use |
|------|-----|
| `get_accounts` | Account balances (includes account IDs) |
| `get_transactions` | Query with `limit`, `start_date`, `end_date` |
| `get_transaction_categories` | Get category IDs for creating transactions |
| `create_transaction` | Add manual entry (see params below) |
| `delete_transaction` | ⚠️ Requires approval |

## Creating Transactions

`create_transaction` requires these parameters:
- `account_id` (string) - Get from `get_accounts`
- `amount` (number) - Positive for income, negative for expenses
- `merchant_name` (string) - Name of the merchant
- `category_id` (string) - Get from `get_transaction_categories`
- `date` (string) - Format: YYYY-MM-DD
- `notes` (string, optional) - Additional notes

Example:
```json
{
  "account_id": "192069965128778350",
  "amount": -25.50,
  "merchant_name": "Coffee Shop",
  "category_id": "184644016420536591",
  "date": "2025-12-15",
  "notes": "Team coffee"
}
```

## Auth Error

If auth fails → User must run `python login_setup.py`
