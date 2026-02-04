# All Tools Reference

## Authentication
| Tool | Description |
|------|-------------|
| `setup_authentication` | Get setup instructions |
| `check_auth_status` | Check if authenticated |
| `debug_session_loading` | Debug keyring issues |

## Accounts (10 tools)
| Tool | Description | Safety |
|------|-------------|--------|
| `get_accounts` | List all accounts | Read |
| `get_account_holdings` | Investment holdings | Read |
| `get_account_history` | Balance over time | Read |
| `get_account_type_options` | Available types | Read |
| `create_manual_account` | Create cash/manual account | Write |
| `update_account` | Modify account | Write |
| `delete_account` | Remove account | ⚠️ Approval |
| `refresh_accounts` | Trigger refresh | Read |
| `request_accounts_refresh_and_wait` | Blocking refresh | Read |
| `is_accounts_refresh_complete` | Check refresh status | Read |

## Transactions (11 tools)
| Tool | Description | Safety |
|------|-------------|--------|
| `get_transaction_stats` | **PRIMARY ANALYTICS**. Returns sum/count with filters. | Read |
| `search_transactions` | **PRIMARY SEARCH**. Keyword search across all fields. | Read |
| `get_transactions` | Query list of full transaction objects. | Read |
| `get_transaction_details` | Single transaction | Read |
| `get_transaction_splits` | Split info | Read |
| `get_transactions_summary` | Aggregated data (global only) | Read |
| `get_recurring_transactions` | Subscriptions | Read |
| `create_transaction` | Add transaction (see params below) | Write |
| `update_transaction` | Modify transaction | Write |
| `update_transaction_splits` | Modify splits | Write |
| `delete_transaction` | Remove transaction | ⚠️ Approval |

### create_transaction Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | string | Yes | Account ID from `get_accounts` |
| `amount` | number | Yes | Positive=income, Negative=expense |
| `merchant_name` | string | Yes | Merchant/payee name |
| `category_id` | string | Yes | Category ID from `get_transaction_categories` |
| `date` | string | Yes | Format: YYYY-MM-DD |
| `notes` | string | No | Optional notes |

## Categories (5 tools)
| Tool | Description | Safety |
|------|-------------|--------|
| `get_transaction_categories` | List categories | Read |
| `get_transaction_category_groups` | List groups | Read |
| `create_transaction_category` | Add category | Write |
| `delete_transaction_category` | Remove category | ⚠️ Approval |
| `delete_transaction_categories` | Bulk remove | ⚠️ Approval |

## Tags (3 tools)
| Tool | Description | Safety |
|------|-------------|--------|
| `get_transaction_tags` | List tags | Read |
| `create_tag` | Add tag | Write |
| `set_transaction_tags` | Assign to transaction | Write |

## Budgets (2 tools)
| Tool | Description | Safety |
|------|-------------|--------|
| `get_budgets` | View budgets | Read |
| `set_budget_amount` | Update budget | Write |

## Analytics (2 tools)
| Tool | Description | Safety |
|------|-------------|--------|
| `get_cashflow` | Income vs expenses | Read |
| `get_cashflow_summary` | Aggregated cashflow | Read |

## Other (3 tools)
| Tool | Description | Safety |
|------|-------------|--------|
| `get_institutions` | Linked institutions | Read |
| `get_subscription_details` | Monarch subscription | Read |
| `upload_account_balance_history` | Import CSV | ⚠️ Approval |

## Safety Tools (3 tools)
| Tool | Description |
|------|-------------|
| `get_safety_stats` | View operation counts |
| `enable_emergency_stop` | Block ALL writes |
| `disable_emergency_stop` | Resume writes |
