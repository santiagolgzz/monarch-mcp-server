# All Tools Reference

Tools are registered in this order. Agents see earlier tools first, so lightweight/diagnostic tools come before heavyweight/write tools.

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
| 7 | `enable_emergency_stop` | Block ALL writes immediately | ⚠️ Action |
| 8 | `disable_emergency_stop` | Resume writes after e-stop | ⚠️ Action |

## Transactions (13 tools)
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
| 18 | `create_transaction` | Add transaction | Write |
| 19 | `update_transaction` | Modify transaction | Write |
| 20 | `delete_transaction` | Remove transaction | ⚠️ Approval |
| 21 | `update_transaction_splits` | Modify splits | Write |

### create_transaction Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | string | Yes | Account ID from `get_accounts` |
| `amount` | number | Yes | Positive=income, Negative=expense |
| `merchant_name` | string | Yes | Merchant/payee name |
| `category_id` | string | Yes | Category ID from `get_transaction_categories` |
| `date` | string | Yes | Format: YYYY-MM-DD |
| `notes` | string | No | Optional notes |

## Accounts (11 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 22 | `get_accounts` | List all accounts | Read |
| 23 | `get_account_holdings` | Investment holdings | Read |
| 24 | `get_account_history` | One account's balance over time | Read |
| 25 | `get_recent_account_balances` | All accounts daily balances (last 31 days) | Read |
| 26 | `get_account_snapshots_by_type` | Net values by account type (month/year) | Read |
| 27 | `get_aggregate_snapshots` | Daily aggregate net value | Read |
| 28 | `get_account_type_options` | Available types for creation | Read |
| 29 | `create_manual_account` | Create cash/manual account | Write |
| 30 | `update_account` | Modify account | Write |
| 31 | `delete_account` | Remove account | ⚠️ Approval |
| 32 | `upload_account_balance_history` | Import CSV history | ⚠️ Approval |

## Budgets (2 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 33 | `get_budgets` | View budgets | Read |
| 34 | `set_budget_amount` | Update budget amount | Write |

## Categories (6 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 35 | `get_transaction_categories` | All categories | Read |
| 36 | `get_transaction_category_groups` | Category groups | Read |
| 37 | `get_transaction_tags` | All tags | Read |
| 38 | `create_transaction_category` | Add category | Write |
| 39 | `delete_transaction_category` | Remove category | ⚠️ Approval |
| 40 | `delete_transaction_categories` | Bulk remove categories | ⚠️ Approval |

## Tags (2 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 41 | `create_tag` | Add tag | Write |
| 42 | `set_transaction_tags` | Assign tags to transaction | Write |

## Refresh (3 tools)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 43 | `is_accounts_refresh_complete` | Check refresh status | Read |
| 44 | `refresh_accounts` | Trigger account refresh | Read |
| 45 | `request_accounts_refresh_and_wait` | Blocking refresh | Read |

## Server (1 tool)
| # | Tool | Description | Safety |
|---|------|-------------|--------|
| — | `setup_authentication` | Get auth setup instructions | Read |

**Note:** `setup_authentication` is registered on the server directly, not via `register_tools()`. It's available in stdio mode only (not HTTP/OAuth mode). Total: 45 shared tools + 1 server tool = 46 registered in stdio mode, 45 in HTTP mode.
