# Changelog

## [2.0.0] - 2025-02-03

### Added - HTTP/SSE Server
- **HTTP Transport**: Starlette-based server for remote MCP access via Server-Sent Events
- **GitHub OAuth**: Secure authentication for multi-user deployments
- **Docker Support**: Production-ready Dockerfile and docker-compose.yml
- **CD Pipeline**: Automated deployment to Google Cloud Run

### Added - Modular Architecture
- **tools/ Package**: Refactored monolithic server.py into organized modules:
  - `accounts.py` - Account management tools
  - `transactions.py` - Transaction tools
  - `categories.py` - Category and tag tools
  - `budgets.py` - Budget and cashflow tools
  - `safety.py` - Safety monitoring tools
  - `refresh.py` - Account refresh tools
  - `metadata.py` - Institution and subscription tools
- **client.py**: Dedicated Monarch Money client initialization module
- **Shared Utilities**: Common tool handler decorator with consistent error handling

### Added - Security & Session Management
- **Keyring Integration**: Store auth tokens in system keyring (macOS Keychain, Windows Credential Manager, Linux Secret Service)
- **Session Persistence**: Long-lived sessions with cookie preservation for MFA bypass
- **Actionable Errors**: Clear error messages with setup instructions

### Changed - CI/CD
- **Python Support**: Now tests Python 3.11, 3.12, 3.13, and 3.14
- **Type Checking**: Switched from mypy to ty (Astral's fast type checker)
- **Test Coverage**: Improved from ~70% to 90%+

### Changed - Documentation
- **README**: Complete rewrite focusing on ease-of-use
- **TOOLS.md**: New comprehensive tool reference
- **DEPLOYMENT.md**: HTTP/SSE deployment guide for multiple platforms

---

## [1.1.0] - 2025-01-30

### Added - Code Quality
- **Test Suite**: Comprehensive pytest test suite with 60+ test cases
- **CI Pipeline**: GitHub Actions for testing, formatting, type checking
- **Custom Exceptions**: `MonarchMCPError` hierarchy for specific error types

### Added - Utility Module
- `validate_date_format`, `validate_positive_amount`, `validate_non_empty_string`
- `format_result` and `format_error` helpers
- Cross-platform config path utilities

### Changed
- **Python Support**: Lowered requirement to Python 3.10+
- **Performance**: Persistent ThreadPoolExecutor for async operations

---

## [1.0.0] - 2025-01-29

### Added - 40+ Tools
Complete Monarch Money API coverage:

**Account Management**
- `get_account_history` - Daily balance history
- `get_account_type_options` - Available account types
- `create_manual_account`, `update_account`, `delete_account`
- `request_accounts_refresh_and_wait`, `is_accounts_refresh_complete`

**Transactions**
- `get_transaction_details`, `get_transaction_splits`
- `get_transactions_summary`, `get_recurring_transactions`
- `update_transaction_splits`, `delete_transaction`

**Categories & Tags**
- `get_transaction_categories`, `get_transaction_category_groups`
- `create_transaction_category`, `delete_transaction_category`, `delete_transaction_categories`
- `get_transaction_tags`, `create_tag`, `set_transaction_tags`

**Budgets & Analytics**
- `set_budget_amount`, `get_cashflow_summary`

**Other**
- `get_institutions`, `get_subscription_details`
- `upload_account_balance_history`

### Added - Safety System
- User approval for destructive operations
- Emergency stop capability
- Operation audit logging with rollback information
- Configurable safety rules

---

## Original

Based on [monarch-mcp-server](https://github.com/robcerda/monarch-mcp-server) by Rob Cerda, which provided the foundation with core authentication and basic account/transaction tools.
