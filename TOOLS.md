# Tools Reference

Complete reference for all 40+ tools available in the Monarch Money MCP Server.

## Table of Contents

- [Account Management](#account-management)
- [Transactions](#transactions)
- [Categories & Tags](#categories--tags)
- [Budgets & Analytics](#budgets--analytics)
- [Safety & Monitoring](#safety--monitoring)
- [Other](#other)

---

## Account Management

### get_accounts
Get all linked financial accounts with balances and institution info.

**Parameters:** None

**Returns:** List of accounts with id, name, type, balance, institution, is_active

---

### get_account_holdings
Get investment holdings for a specific account.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `account_id` | string | Yes | The account ID |

---

### get_account_history
Get daily account balance history over time.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `account_id` | string | Yes | The account ID |
| `start_date` | string | No | Start date (YYYY-MM-DD) |
| `end_date` | string | No | End date (YYYY-MM-DD) |

---

### get_account_type_options
Get all available account types and subtypes for creating manual accounts.

**Parameters:** None

---

### create_manual_account
Create a manual account not linked to a financial institution.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `account_name` | string | Yes | Display name for the account |
| `account_type` | string | Yes | Account type (use get_account_type_options) |
| `current_balance` | float | Yes | Starting balance |
| `account_subtype` | string | No | Account subtype |

---

### update_account
Update account settings or balance.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `account_id` | string | Yes | The account ID |
| `name` | string | No | New account name |
| `balance` | float | No | New balance |
| `account_type` | string | No | New account type |

---

### delete_account
Delete an account from Monarch Money.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `account_id` | string | Yes | The account ID |

**Safety:** Requires approval

---

### refresh_accounts
Request account data refresh from financial institutions (non-blocking).

**Parameters:** None

---

### request_accounts_refresh_and_wait
Request account refresh and wait for completion (blocking).

**Parameters:** None

---

### is_accounts_refresh_complete
Check if account refresh is complete.

**Parameters:** None

---

## Transactions

### get_transactions
Get transactions with filtering options.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `limit` | int | No | Max results (default: 100) |
| `offset` | int | No | Pagination offset |
| `start_date` | string | No | Start date (YYYY-MM-DD) |
| `end_date` | string | No | End date (YYYY-MM-DD) |
| `account_id` | string | No | Filter by account |
| `category_id` | string | No | Filter by category |
| `search` | string | No | Search term |
| `min_amount` | float | No | Minimum amount |
| `max_amount` | float | No | Maximum amount |

---

### search_transactions
Search for transactions using keywords.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | Search term |
| `limit` | int | No | Max results (default: 20) |

---

### get_transaction_details
Get detailed information about a specific transaction.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `transaction_id` | string | Yes | The transaction ID |

---

### get_transaction_splits
Get split information for a transaction.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `transaction_id` | string | Yes | The transaction ID |

---

### get_transactions_summary
Get aggregated transaction summary data.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `start_date` | string | No | Start date (YYYY-MM-DD) |
| `end_date` | string | No | End date (YYYY-MM-DD) |

---

### get_transaction_stats
Get high-level statistics (sum, count) without listing transactions.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `start_date` | string | No | Start date (YYYY-MM-DD) |
| `end_date` | string | No | End date (YYYY-MM-DD) |
| `category_id` | string | No | Filter by category |
| `account_id` | string | No | Filter by account |

---

### get_recurring_transactions
Get all recurring transactions.

**Parameters:** None

---

### create_transaction
Create a new transaction.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `account_id` | string | Yes | The account ID |
| `amount` | float | Yes | Amount (negative for expenses) |
| `merchant_name` | string | Yes | Merchant/payee name |
| `category_id` | string | Yes | Category ID |
| `date` | string | Yes | Date (YYYY-MM-DD) |
| `notes` | string | No | Optional notes |

---

### update_transaction
Update an existing transaction.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `transaction_id` | string | Yes | The transaction ID |
| `amount` | float | No | New amount |
| `description` | string | No | New description |
| `category_id` | string | No | New category |
| `date` | string | No | New date (YYYY-MM-DD) |

---

### update_transaction_splits
Update or create transaction splits.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `transaction_id` | string | Yes | The transaction ID |
| `splits_data` | string | Yes | JSON string of split data |

**Safety:** Requires approval

---

### delete_transaction
Delete a transaction.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `transaction_id` | string | Yes | The transaction ID |

**Safety:** Requires approval

---

## Categories & Tags

### get_transaction_categories
Get all transaction categories.

**Parameters:** None

---

### get_transaction_category_groups
Get all category groups.

**Parameters:** None

---

### create_transaction_category
Create a new category.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Category name |
| `group_id` | string | Yes | Parent group ID |

---

### delete_transaction_category
Delete a category.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `category_id` | string | Yes | The category ID |

**Safety:** Requires approval

---

### delete_transaction_categories
Delete multiple categories at once.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `category_ids` | string | Yes | Comma-separated category IDs |

**Safety:** Requires approval

---

### get_transaction_tags
Get all transaction tags.

**Parameters:** None

---

### create_tag
Create a new tag.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Tag name |
| `color` | string | No | Hex color (e.g., #FF5733) |

---

### set_transaction_tags
Assign tags to a transaction.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `transaction_id` | string | Yes | The transaction ID |
| `tag_ids` | string | Yes | Comma-separated tag IDs |

---

## Budgets & Analytics

### get_budgets
Get budget information including spent amounts and remaining balances.

**Parameters:** None

---

### set_budget_amount
Set or update budget amount for a category.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `category_id` | string | Yes | The category ID |
| `amount` | float | Yes | Budget amount (0 to clear) |

---

### get_cashflow
Get cashflow analysis over a date range.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `start_date` | string | No | Start date (YYYY-MM-DD) |
| `end_date` | string | No | End date (YYYY-MM-DD) |

---

### get_cashflow_summary
Get aggregated cashflow summary.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `start_date` | string | No | Start date (YYYY-MM-DD) |
| `end_date` | string | No | End date (YYYY-MM-DD) |

---

## Safety & Monitoring

### get_safety_stats
View operation statistics and safety status.

**Parameters:** None

**Returns:** Daily operation counts, emergency stop status, approval requirements

---

### get_recent_operations
View recent write operations with rollback information.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `limit` | int | No | Max results (default: 10, max: 50) |

---

### get_rollback_suggestions
Get detailed rollback instructions for a recent operation.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `operation_index` | int | No | 0 = most recent (default) |

---

### enable_emergency_stop
Block ALL write operations immediately.

**Parameters:** None

---

### disable_emergency_stop
Re-enable write operations after emergency stop.

**Parameters:** None

---

## Other

### get_institutions
Get all linked financial institutions.

**Parameters:** None

---

### get_subscription_details
Get Monarch Money subscription status (paid/trial).

**Parameters:** None

---

### upload_account_balance_history
Upload historical account balance data from CSV.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `account_id` | string | Yes | The account ID |
| `csv_data` | string | Yes | CSV content |

**Safety:** Requires approval

---

### setup_authentication
Get authentication setup instructions.

**Parameters:** None

---

### check_auth_status
Check if authenticated with Monarch Money.

**Parameters:** None

---

## Date Formats

All dates use `YYYY-MM-DD` format (e.g., "2024-01-15").

## Amount Conventions

- **Positive amounts**: Income/deposits
- **Negative amounts**: Expenses/withdrawals

## Safety Levels

Tools marked with **Safety: Requires approval** will prompt for confirmation before executing. This protects against accidental data loss.

See [ROLLBACK_GUIDE.md](ROLLBACK_GUIDE.md) for information on undoing operations.
