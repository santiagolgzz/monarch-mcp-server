# Changelog

## [Unreleased]

### Added
- **`refresh_accounts` / `request_accounts_refresh_and_wait` / `is_accounts_refresh_complete`**: Added `account_ids` so a refresh can target one account, a subset, or all (omit for all). The wait variant also gained `timeout` and `delay`.
- **`set_budget_amount`**: Added `category_group_id` (budget a whole group), `timeframe`, `start_date`, and `apply_to_future`. Exactly one of `category_id` / `category_group_id` is required, validated with a clear error instead of the SDK's generic one.
- **`upload_attachment`** *(new tool)*: Attach a file to a transaction. Content is base64-encoded since MCP carries text, with a 10 MiB decoded size limit.
- **`get_credit_history`** *(new tool)*: Credit score history.
- **`update_transaction`**: Exposed `goal_id`, `hide_from_reports`, `needs_review`, and `notes`.
- **`update_account`**: Exposed `account_sub_type`, `include_in_net_worth`, `hide_from_summary_list`, and `hide_transactions_from_reports`.
- **`create_transaction_category`**: Exposed `rollover_start_month`.
- **`upload_account_balance_history`**: Added `timeout` and `delay`.
- **`get_transactions`**: Exposed eight server-side SDK filters that previously had no way to be reached from a tool call — `tag_ids`, `has_attachments`, `has_notes`, `hidden_from_reports`, `is_split`, `is_recurring`, `imported_from_mint`, `synced_from_institution`. All default to no filtering.
- **`get_recurring_transactions`**: Added `start_date` / `end_date` to limit results to a period.
- **`get_budgets`**: Added `start_date` / `end_date` to select the budget period.
- **`get_transaction_details`**: Added `redirect_posted` (default `true`, matching the SDK and the Monarch app) to control whether a pending transaction that has since posted redirects to the posted one.
- **SDK coverage ratchet**: `scripts/sdk_coverage.py` reports SDK surface this server does not expose, and fails the build on regression. Enforced at commit time and in CI.

### Fixed
- **`get_transactions_summary`**: The tool advertised `start_date` / `end_date` and splatted them into an SDK call that accepts no arguments, so supplying either raised `TypeError`. The underlying call is not date-filterable; the parameters are removed and the docstring points to `get_transaction_stats` for date-ranged aggregates. Found by converting `**kwargs` call sites to explicit arguments for the coverage ratchet.
- **`create_transaction_category`**: `rollover_start_month` now defaults to the first of the current month computed per call. The SDK's own default is evaluated once at import, so a long-running server drifted to a stale month.
- **`create_transaction`**: Added optional `update_balance` parameter (default `false`) so manual transactions can affect the account balance, matching Monarch's "impact balance" checkbox (#15).

## [1.2.0] - 2026-04-12

### Changed
- **SDK**: Switched from `monarchmoney` (stale) to `monarchmoneycommunity` (actively maintained community fork). Same import path, no monkey-patch needed.
- **Dependencies**: Pinned all dependency versions for reproducible builds.
- **`upload_account_balance_history`**: Now parses CSV text into structured `BalanceHistoryRow` objects as required by the community SDK.
- **`create_transaction_category`**: Added optional `icon`, `rollover_enabled`, `rollover_type` parameters.
- **`get_transaction_tags`**: Hardened response key handling to support `transactionTags`, `householdTransactionTags`, and `tags` keys.

### Added
- **`add_transaction_tag`** tool: Appends a tag to a transaction while preserving existing tags.
- **`categorize_transaction`** tool: Dedicated tool for assigning a category to a transaction.
- **WSL keyring fallback**: Smart backend detection (`_keyring_available()`) with file-based token storage (`~/.mm/token`, 0o600 permissions) when system keyring is unavailable.
- **Auth priority fix**: `MONARCH_TOKEN` env var now correctly overrides stale native sessions in `get_authenticated_client()`.
- **`delete_token()` guard**: Skips destructive token cleanup when `MONARCH_TOKEN` env var is set (env tokens are ephemeral).
- Safety config: `add_transaction_tag` and `categorize_transaction` added to `warn_before_execute`.
- Rollback metadata for both new operations in `SafetyGuard`.

## [Unreleased]

### Changed
- MCP tool responses now use native structured values (dict/list/str) end-to-end.
- Removed legacy JSON-string assumptions in tests and safety logging paths.
- Hard cutover: downstream consumers should not call `json.loads(...)` on tool results unless the tool explicitly returns a string.

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
