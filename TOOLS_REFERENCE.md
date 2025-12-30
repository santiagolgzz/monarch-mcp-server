# Quick Tools Reference

## All 37 Available Tools

### Authentication & Setup (3 tools)
1. `setup_authentication` - Get authentication setup instructions
2. `check_auth_status` - Check if authenticated
3. `debug_session_loading` - Debug keyring session issues

### Account Management (10 tools)
4. `get_accounts` - View all linked accounts
5. `get_account_holdings` - Get securities in investment accounts
6. `get_account_history` - Track daily balance history ⭐ NEW
7. `get_account_type_options` - Get available account types ⭐ NEW
8. `create_manual_account` - Create manual accounts ⭐ NEW
9. `update_account` - Update account settings ⭐ NEW
10. `delete_account` - Delete accounts ⭐ NEW
11. `refresh_accounts` - Request account refresh (non-blocking)
12. `request_accounts_refresh_and_wait` - Blocking refresh ⭐ NEW
13. `is_accounts_refresh_complete` - Check refresh status ⭐ NEW

### Transaction Management (9 tools)
14. `get_transactions` - Get transactions with filters
15. `get_transaction_details` - Get detailed transaction info ⭐ NEW
16. `get_transaction_splits` - Get split transaction data ⭐ NEW
17. `get_transactions_summary` - Aggregated transaction data ⭐ NEW
18. `get_recurring_transactions` - Get recurring payments ⭐ NEW
19. `create_transaction` - Add new transactions
20. `update_transaction` - Modify existing transactions
21. `update_transaction_splits` - Create/update splits ⭐ NEW
22. `delete_transaction` - Remove transactions ⭐ NEW

### Categories (6 tools)
23. `get_transaction_categories` - View all categories ⭐ NEW
24. `get_transaction_category_groups` - View category groups ⭐ NEW
25. `create_transaction_category` - Create new categories ⭐ NEW
26. `delete_transaction_category` - Delete single category ⭐ NEW
27. `delete_transaction_categories` - Delete multiple categories ⭐ NEW

### Tags (3 tools)
28. `get_transaction_tags` - View all tags ⭐ NEW
29. `create_tag` - Create new tags with colors ⭐ NEW
30. `set_transaction_tags` - Assign tags to transactions ⭐ NEW

### Budgets (2 tools)
31. `get_budgets` - View budget information
32. `set_budget_amount` - Set/update budget amounts ⭐ NEW

### Analytics (3 tools)
33. `get_cashflow` - Analyze income/expenses
34. `get_cashflow_summary` - Aggregated cashflow data ⭐ NEW

### Other (3 tools)
35. `get_institutions` - View linked institutions ⭐ NEW
36. `get_subscription_details` - Check subscription status ⭐ NEW
37. `upload_account_balance_history` - Import CSV data ⭐ NEW

---

**Legend**: ⭐ NEW = Added in Extended Edition

**Total**: 37 tools (40 including debug/auth tools)
**Original**: 10 tools (13 including debug tools)
**New**: 27 tools added (+270% increase)

## Most Useful New Tools

### For Personal Finance Management
- `create_manual_account` - Track cash, gift cards, etc.
- `get_account_history` - See how balances changed over time
- `set_budget_amount` - Set spending limits
- `get_recurring_transactions` - Track subscriptions
- `create_tag` + `set_transaction_tags` - Organize transactions

### For Data Organization
- `create_transaction_category` - Custom expense categories
- `delete_transaction_categories` - Bulk cleanup
- `update_transaction_splits` - Split shared expenses
- `get_transactions_summary` - Quick spending overview

### For Advanced Users
- `get_institutions` - Institution metadata
- `upload_account_balance_history` - Import historical data
- `get_subscription_details` - API access info
- `request_accounts_refresh_and_wait` - Synchronous refresh

## Quick Start Examples

```bash
# View everything you have
get_accounts
get_transaction_categories
get_transaction_tags
get_budgets

# Create a manual account
create_manual_account(
    account_name="Cash Wallet",
    account_type="cash",
    current_balance=150.00
)

# Set a budget
set_budget_amount(category_id="groceries_id", amount=500.00)

# Create and use a tag
create_tag(name="Tax Deductible", color="#FF5733")
set_transaction_tags(transaction_id="txn_id", tag_ids="tag_id")

# Track account history
get_account_history(account_id="acct_id", start_date="2024-01-01")
```
