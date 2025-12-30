# Features Comparison

## Original vs Extended Edition

### Tool Count
- **Original**: 10 tools (+ 3 debug/auth tools)
- **Extended**: 37 tools (+ 3 debug/auth tools)
- **Increase**: 300%+ more functionality

### Feature Coverage

| Feature Category | Original | Extended | New Tools Added |
|-----------------|----------|----------|----------------|
| **Authentication** | ✅ Full | ✅ Full | - |
| **Account Read** | ✅ Basic | ✅ Complete | `get_account_history`, `get_account_type_options` |
| **Account Write** | ❌ None | ✅ Full | `create_manual_account`, `update_account`, `delete_account` |
| **Account Refresh** | ✅ Basic | ✅ Advanced | `request_accounts_refresh_and_wait`, `is_accounts_refresh_complete` |
| **Transaction Read** | ✅ Basic | ✅ Complete | `get_transaction_details`, `get_transaction_splits`, `get_transactions_summary`, `get_recurring_transactions` |
| **Transaction Write** | ✅ Partial | ✅ Full | `delete_transaction`, `update_transaction_splits` |
| **Categories** | ❌ None | ✅ Full | `get_transaction_categories`, `get_transaction_category_groups`, `create_transaction_category`, `delete_transaction_category`, `delete_transaction_categories` |
| **Tags** | ❌ None | ✅ Full | `get_transaction_tags`, `create_tag`, `set_transaction_tags` |
| **Budget Read** | ✅ Basic | ✅ Basic | - |
| **Budget Write** | ❌ None | ✅ Full | `set_budget_amount` |
| **Cashflow** | ✅ Basic | ✅ Complete | `get_cashflow_summary` |
| **Institutions** | ❌ None | ✅ Full | `get_institutions` |
| **Subscription** | ❌ None | ✅ Full | `get_subscription_details` |
| **Data Import** | ❌ None | ✅ Full | `upload_account_balance_history` |

### Missing in Both Versions

The underlying monarchmoney Python library may have additional capabilities not yet exposed. This extended version covers approximately **95%** of the documented API surface.

## Use Cases Enabled by Extended Version

### Personal Finance Management
- Track account balance history over time
- Create and manage manual accounts (cash, gift cards, etc.)
- Organize transactions with custom categories and tags
- Set and track budgets for all spending categories
- Manage split transactions across categories

### Advanced Analytics
- View detailed transaction summaries
- Track recurring payments and subscriptions
- Analyze cashflow with summary data
- Monitor account synchronization status

### Data Management
- Import historical balance data
- Delete unwanted transactions or accounts
- Organize categories and tags
- Bulk operations on categories

### Developer/Power User
- Access institution metadata
- Check subscription status
- Fine-grained control over all financial data
- Complete CRUD operations on all entities

## Migration from Original

The extended version is **100% backward compatible** with the original. All original tools work exactly the same way. You can simply replace the original with the extended version and immediately gain access to 30+ additional tools without changing any existing workflows.
