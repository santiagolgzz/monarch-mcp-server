# Financial Analysis Patterns

Step-by-step patterns for common financial analysis tasks using Monarch Money MCP tools.

## Calculating Balance Changes

Use `get_account_history` to compare balances over time. Do not sum transaction amounts—this misses transfers, adjustments, and sync corrections.

```python
# Get account balance change for a period
history = get_account_history(account_id="123456")

# Find balances at start and end dates
start_balance = next(h["signedBalance"] for h in history if h["date"] <= "2025-01-01")
end_balance = next(h["signedBalance"] for h in history if h["date"] <= "2025-12-31")

net_change = end_balance - start_balance
```

For multi-account analysis (e.g., total liquid cash), repeat for each account and sum the changes.

## Calculating Savings Rate

Do not use `get_cashflow_summary` savings rate—it only captures post-paycheck cash accumulation and misses retirement contributions.

**Correct formula:**
```
Gross Income = Total salary/wages before deductions

Total Savings = Retirement contributions (401k, IRA)
              + HSA contributions
              + Net cash accumulation (from account history)
              + Loan principal paid (equity building)
              + Other asset contributions

Savings Rate = Total Savings / Gross Income
```

Get retirement contributions efficiently:
```python
# Use get_transaction_stats to find total contributions without listing transactions
stats = get_transaction_stats(
    start_date="2025-01-01", 
    end_date="2025-12-31",
    category_id="paychecks_category_id"  # Filter by category if known
)
# sum_income will capture contributions if they are categorized as such
```

If you need precise filtering by account name or keywords, use `search_transactions`:
```python
results = search_transactions(query="401k contribution")
```

## Calculating Net Worth

1. Get all accounts with `get_accounts`
2. Check for account duplication before summing
3. Use realistic asset values, not inflated estimates

**Account duplication patterns:**
- Manual "contributions" account + linked "full balance" account for same 401k
- Manual tracking account + linked brokerage for same DSPP/ESPP
- Pre-vesting contributions tracked separately from vested balance

Ask user which accounts to include. Do not assume all accounts should be summed.

**Vehicle values:** VinAudit values in Monarch may be inflated. Cross-reference with KBB or Edmunds for vehicles, especially when calculating equity.

## Session Management

Auth tokens expire during long analysis sessions. If `get_*` calls return 401 errors:

1. Inform user: "Session expired. Please run `python login_setup.py`"
2. Wait for confirmation
3. Retry the failed operation

Batch related queries together to minimize timeout risk during complex analysis.

## Working with User Context

Before performing financial analysis:

1. Check if user has a financial context file documenting account structure
2. Ask about account relationships if unclear
3. Use user-provided values over API data when they conflict—users often have better information about manual accounts, external valuations, or adjustments not reflected in Monarch
