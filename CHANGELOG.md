# Changelog

## [1.0.0] - Extended Edition - 2025-01-29

### Major Enhancement
Extended the Monarch Money MCP Server from 10 tools to **40+ tools**, providing comprehensive coverage of the Monarch Money API.

### Added - Account Management (7 new tools)
- `get_account_history` - Get daily account balance history with date filtering
- `get_account_type_options` - Get all available account types and subtypes
- `create_manual_account` - Create manual accounts not linked to institutions
- `update_account` - Update account name, balance, or type
- `delete_account` - Delete accounts
- `request_accounts_refresh_and_wait` - Blocking account refresh with completion wait
- `is_accounts_refresh_complete` - Check account refresh status

### Added - Transaction Management (7 new tools)
- `get_transaction_details` - Get detailed information about specific transactions
- `get_transaction_splits` - Get split information for transactions
- `get_transactions_summary` - Get aggregated transaction summary data
- `get_recurring_transactions` - Get all recurring transactions
- `update_transaction_splits` - Create or update transaction splits
- `delete_transaction` - Delete transactions

### Added - Categories & Tags (8 new tools)
- `get_transaction_categories` - Get all transaction categories
- `get_transaction_category_groups` - Get all category groups
- `create_transaction_category` - Create new categories
- `delete_transaction_category` - Delete single category
- `delete_transaction_categories` - Delete multiple categories at once
- `get_transaction_tags` - Get all transaction tags
- `create_tag` - Create new tags with optional colors
- `set_transaction_tags` - Assign tags to transactions

### Added - Budgets & Analytics (2 new tools)
- `set_budget_amount` - Set or update budget amounts for categories
- `get_cashflow_summary` - Get aggregated cashflow summary data

### Added - Other Features (3 new tools)
- `get_institutions` - Get all linked financial institutions
- `get_subscription_details` - Get Monarch Money subscription status
- `upload_account_balance_history` - Upload historical balance data from CSV

### Enhanced
- Comprehensive documentation with 40+ tool reference table
- Extended usage examples covering all new features
- Organized tool categories in README for better navigation
- Updated project metadata to reflect extended capabilities

### Original Tools (Maintained)
- `setup_authentication` - Authentication setup instructions
- `check_auth_status` - Check authentication status
- `debug_session_loading` - Debug session loading
- `get_accounts` - Get all financial accounts
- `get_transactions` - Get transactions with filtering
- `get_budgets` - Get budget information
- `get_cashflow` - Get cashflow analysis
- `get_account_holdings` - Get investment holdings
- `create_transaction` - Create new transactions
- `update_transaction` - Update existing transactions
- `refresh_accounts` - Request account data refresh

## Original Repository
This is an extended fork of [monarch-mcp-server](https://github.com/robcerda/monarch-mcp-server) by Rob Cerda.

Original repository provides the foundation with core authentication, account access, and transaction management features.
