# All Tools Reference

Tools are registered in this order. Agents see earlier tools first, so lightweight/diagnostic tools come before heavyweight/write tools.

The **Safety** column uses the tiers defined in [safety.md](safety.md):

- **Read** — no protection, no audit entry.
- **Recorded** — executes immediately, recorded in the audit log, no warning.
- **Warn** — shows a warning before executing, recorded.
- **Approval** — blocked until the user approves, recorded.
- **Action** — changes safety state itself (emergency stop).

## Contents
- Metadata (3) — auth status, subscription, institutions
- Safety (5) — stats, audit trail, emergency stop
- Transactions (15) — stats, summaries, CRUD, categorization, attachments
- Accounts (12) — balances, holdings, history, credit, CRUD
- Budgets (2) — view and set amounts
- Categories (6) — categories, category groups, tags
- Tags (3) — create, assign, append
- Refresh (3) — trigger and poll account refresh
- Server (1) — auth setup (stdio only)

## Metadata (3 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 1 | `check_auth_status` | Check if authenticated, shows plan | Read |
| 2 | `get_subscription_details` | Monarch subscription info | Read |
| 3 | `get_institutions` | Linked banks/institutions | Read |

## Safety (5 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 4 | `get_safety_stats` | Operation counts, e-stop status | Read |
| 5 | `get_recent_operations` | Audit trail of recent writes | Read |
| 6 | `get_rollback_suggestions` | Undo guidance for operations | Read |
| 7 | `enable_emergency_stop` | Block ALL writes immediately | Action |
| 8 | `disable_emergency_stop` | Resume writes after e-stop | Action |

## Transactions (15 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 9 | `get_transaction_stats` | **Prefer this.** Aggregates: sum, count, net. | Read |
| 10 | `get_transactions_summary` | Category/period breakdown | Read |
| 11 | `get_recurring_transactions` | Recurring patterns/subscriptions | Read |
| 12 | `get_cashflow` | Income vs expense breakdown with details | Read |
| 13 | `get_cashflow_summary` | Aggregated cashflow totals | Read |
| 14 | `search_transactions` | Keyword search (targeted) | Read |
| 15 | `get_transactions` | Full list with filters (heavyweight) | Read |
| 16 | `get_transaction_details` | Single transaction deep dive | Read |
| 17 | `get_transaction_splits` | One transaction's splits | Read |
| 18 | `upload_attachment` | Attach a file (e.g. receipt) to a transaction | Warn |
| 19 | `create_transaction` | Add transaction | Warn |
| 20 | `update_transaction` | Modify transaction | Warn |
| 21 | `categorize_transaction` | Assign category to transaction | Warn |
| 22 | `delete_transaction` | Remove transaction | Approval |
| 23 | `update_transaction_splits` | Modify splits | Warn |

### create_transaction Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | string | Yes | Account ID from `get_accounts` |
| `amount` | number | Yes | Positive=income, Negative=expense |
| `merchant_name` | string | Yes | Merchant/payee name |
| `category_id` | string | Yes | Category ID from `get_transaction_categories` |
| `date` | string | Yes | Format: YYYY-MM-DD |
| `notes` | string | No | Optional notes |
| `update_balance` | boolean | No | Default `false`. `true` makes the transaction move the account's balance — the "impact balance" checkbox in the Monarch app. A manual transaction recorded with the default leaves the balance untouched. |

### upload_attachment Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `transaction_id` | string | Yes | Transaction to attach the file to |
| `file_content_base64` | string | Yes | The file's bytes, base64-encoded (MCP carries text, not raw bytes) |
| `filename` | string | Yes | File name including extension, e.g. `receipt.pdf` |

## Accounts (12 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 24 | `get_accounts` | List all accounts | Read |
| 25 | `get_account_holdings` | Investment holdings | Read |
| 26 | `get_account_history` | One account's balance over time | Read |
| 27 | `get_recent_account_balances` | All accounts daily balances (last 31 days) | Read |
| 28 | `get_account_snapshots_by_type` | Net values by account type (month/year) | Read |
| 29 | `get_aggregate_snapshots` | Daily aggregate net value | Read |
| 30 | `get_credit_history` | Credit score history (needs credit monitoring on) | Read |
| 31 | `get_account_type_options` | Available types for creation | Read |
| 32 | `create_manual_account` | Create cash/manual account | Warn |
| 33 | `update_account` | Modify account | Warn |
| 34 | `delete_account` | Remove account | Approval |
| 35 | `upload_account_balance_history` | Import CSV history | Approval |

## Budgets (2 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 36 | `get_budgets` | View budgets | Read |
| 37 | `set_budget_amount` | Update budget amount | Warn |

## Categories (6 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 38 | `get_transaction_categories` | All categories | Read |
| 39 | `get_transaction_category_groups` | Category groups | Read |
| 40 | `get_transaction_tags` | All tags | Read |
| 41 | `create_transaction_category` | Add category (supports icon, rollover) | Recorded |
| 42 | `delete_transaction_category` | Remove category | Approval |
| 43 | `delete_transaction_categories` | Bulk remove categories | Approval |

### create_transaction_category Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Category name |
| `group_id` | string | Yes | Parent group ID from `get_transaction_category_groups` |
| `icon` | string | No | Emoji icon for the category |
| `rollover_enabled` | boolean | No | Whether budget rollover is enabled |
| `rollover_type` | string | No | Rollover type (e.g. "monthly") |
| `rollover_start_month` | string | No | Month the rollover starts from, YYYY-MM-DD |

## Tags (3 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 44 | `create_tag` | Add tag | Recorded |
| 45 | `set_transaction_tags` | Replace all tags on a transaction | Recorded |
| 46 | `add_transaction_tag` | Append tag without removing existing | Warn |

## Refresh (3 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 47 | `is_accounts_refresh_complete` | Check refresh status | Read |
| 48 | `refresh_accounts` | Trigger account refresh | Read |
| 49 | `request_accounts_refresh_and_wait` | Blocking refresh | Read |

## Server (1 tool)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| — | `setup_authentication` | Get auth setup instructions | Read |

**Note:** `setup_authentication` is registered on the server directly, not via `register_tools()`. Available in stdio mode only. Total: 49 shared tools + 1 server tool = 50 in stdio mode, 49 in HTTP mode.

---

**Keeping this file honest:** `tests/test_skill_accuracy.py` checks the tool names, counts, numbering, safety tiers, and the parameter tables above against the registered tools and `SafetyConfig` defaults. If you add or rename a tool, that test fails until this file is updated.
