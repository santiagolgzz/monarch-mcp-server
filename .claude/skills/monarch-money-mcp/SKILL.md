---
name: monarch-money-mcp
description: "Queries and manages Monarch Money financial data via MCP tools. Use when checking accounts, transactions, budgets, categories, tags, or any personal finance data from Monarch. Triggers: finances, spending, accounts, budgets, transactions, net worth, savings"
---

# Monarch Money MCP

Access 46 tools for Monarch Money personal finance.
- **[tools.md](references/tools.md)**: Full tool list with registration order
- **[safety.md](references/safety.md)**: Safety tiers and emergency controls
- **[financial-analysis.md](references/financial-analysis.md)**: Analysis guides

## Quick Start

Tools are registered lightweight-first. Prefer aggregates over full lists.

```
check_auth_status             # Always start here — verify connectivity
get_transaction_stats         # Aggregates (sum, count) — usually sufficient
get_transactions_summary      # Category/period breakdown
search_transactions           # Keyword search (targeted, small results)
get_transactions              # Full list with filters (heavyweight — use last)
get_accounts                  # List all accounts
get_budgets                   # Budget vs actual
```

## Safety (CRITICAL)

- **Read-only tools are safe** — All `get_*` and `search_*` tools
- **Destructive ops require approval** — `delete_*` tools prompt user first
- **Emergency stop** — `enable_emergency_stop` blocks all writes
- **Dates** — Always YYYY-MM-DD format

## Tool Selection Guide

| Need | Tool | Why |
|------|------|-----|
| "How much did I spend?" | `get_transaction_stats` | Aggregates without listing rows |
| "Show my transactions" | `get_transactions` | Full list with filters |
| "Find a specific charge" | `search_transactions` | Keyword search across fields |
| Account balances | `get_accounts` | Includes account IDs |
| Category IDs for writes | `get_transaction_categories` | Required before `create_transaction` |
| Recurring bills | `get_recurring_transactions` | Subscriptions and patterns |
| Budget progress | `get_budgets` | Budget vs actual |

## Creating Transactions

`create_transaction` requires these parameters:
- `account_id` (string) — Get from `get_accounts`
- `amount` (number) — Positive for income, negative for expenses
- `merchant_name` (string) — Name of the merchant
- `category_id` (string) — Get from `get_transaction_categories`
- `date` (string) — Format: YYYY-MM-DD
- `notes` (string, optional) — Additional notes

## Auth Error

If auth fails → run `check_auth_status` first for diagnostics. If not authenticated, user must run `python login_setup.py`.
