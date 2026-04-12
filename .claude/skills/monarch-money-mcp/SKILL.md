---
name: monarch-money-mcp
description: "Queries and manages Monarch Money financial data via MCP tools — accounts, transactions, budgets, categories, tags, net worth, cashflow, savings rate, holdings, and recurring bills. Use when the user asks about personal finances, spending, income, investments, bank accounts, credit cards, loans, subscriptions, expense tracking, or any Monarch Money data."
---

# Monarch Money MCP

48 tools for Monarch Money personal finance (47 shared + 1 stdio-only).
- **[tools.md](references/tools.md)**: Full tool list with registration order and parameters
- **[safety.md](references/safety.md)**: Safety tiers, emergency controls, and audit trail
- **[financial-analysis.md](references/financial-analysis.md)**: Patterns for balance changes, savings rate, net worth

## Quick Start

Tools are registered lightweight-first. Prefer aggregates over full lists.

```
check_auth_status             # Always start here — verify connectivity
get_transaction_stats         # Aggregates (sum, count) — usually sufficient
get_transactions_summary      # Category/period breakdown
search_transactions           # Keyword search (targeted, small results)
get_transactions              # Full list with filters (heavyweight — only use when no other tool will suffice)
get_accounts                  # List all accounts
get_budgets                   # Budget vs actual
```

## Safety

- **Read-only tools are safe** — All `get_*`, `search_*`, and `is_*` tools
- **8 write ops show warnings** — `create_transaction`, `update_transaction`, `update_transaction_splits`, `create_manual_account`, `update_account`, `set_budget_amount`, `add_transaction_tag`, `categorize_transaction`
- **5 destructive ops require approval** — `delete_transaction`, `delete_account`, `delete_transaction_category`, `delete_transaction_categories`, `upload_account_balance_history`
- **Other write ops** (`create_tag`, `set_transaction_tags`, `create_transaction_category`) are recorded but execute without warning
- **Emergency stop** — `enable_emergency_stop` blocks all writes immediately
- **All dates** — YYYY-MM-DD format

## Tool Selection Guide

| Need | Tool | Why |
|------|------|-----|
| "How much did I spend?" | `get_transaction_stats` | Aggregates without listing rows |
| "Show my transactions" | `get_transactions` | Full list with filters |
| "Find a specific charge" | `search_transactions` | Keyword search across fields |
| Account balances | `get_accounts` | Includes account IDs |
| "Categorize this transaction" | `categorize_transaction` | Dedicated tool, more discoverable than `update_transaction` |
| "Tag this transaction" | `add_transaction_tag` | Appends without removing existing tags |
| Category/tag IDs for writes | `get_transaction_categories` / `get_transaction_tags` | Required before creating transactions or assigning categories/tags |
| Recurring bills | `get_recurring_transactions` | Subscriptions and patterns |
| Budget progress | `get_budgets` | Budget vs actual |
| Net worth over time | `get_aggregate_snapshots` | Daily aggregate across all accounts |

## Similar Tools

| Instead of... | Use... | When... |
|---------------|--------|---------|
| `update_transaction(category_id=...)` | `categorize_transaction` | Only changing the category |
| `set_transaction_tags` | `add_transaction_tag` | Adding a tag without removing existing ones |
| `get_transactions` | `get_transaction_stats` | You need totals, not individual rows |
| `get_cashflow` | `get_cashflow_summary` | You need aggregated totals, not line items |

## Creating Transactions

`create_transaction` requires:
- `account_id` (string) — from `get_accounts`
- `amount` (number) — positive = income, negative = expense
- `merchant_name` (string)
- `category_id` (string) — from `get_transaction_categories`
- `date` (string) — YYYY-MM-DD
- `notes` (string, optional)

## Auth Errors

If any tool returns an auth error, run `check_auth_status` for diagnostics. If not authenticated, the user must run `python login_setup.py`.
