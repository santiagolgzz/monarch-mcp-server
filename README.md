[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/robcerda-monarch-mcp-server-badge.png)](https://mseep.ai/app/robcerda-monarch-mcp-server)

# Monarch Money MCP Server - Extended Edition

A comprehensive Model Context Protocol (MCP) server for integrating with the Monarch Money personal finance platform. This **extended version** provides access to **40+ tools** covering the complete Monarch Money API, including advanced features like transaction splits, category management, tags, manual accounts, and more.

## 🎯 Extended Features

This fork extends the original [monarch-mcp-server](https://github.com/robcerda/monarch-mcp-server) from 10 tools to **40+ tools**, adding:

- ✅ **Account History & Manual Accounts**: Track balance history and create/manage manual accounts
- ✅ **Transaction Splits & Details**: Full support for split transactions and detailed transaction views
- ✅ **Categories & Tags**: Create, manage, and delete categories and tags
- ✅ **Budget Management**: Set and update budget amounts for categories
- ✅ **Advanced Analytics**: Transaction summaries, cashflow summaries, and recurring transactions
- ✅ **Data Import**: Upload historical balance data from CSV files
- ✅ **Institution Management**: View linked financial institutions
- ✅ **Complete CRUD Operations**: Full create, read, update, delete for transactions, accounts, categories

**Original Repository**: https://github.com/robcerda/monarch-mcp-server

**Built with the [MonarchMoney Python library](https://github.com/hammem/monarchmoney) by [@hammem](https://github.com/hammem)** - A fantastic unofficial API for Monarch Money with full MFA support.

<a href="https://glama.ai/mcp/servers/@robcerda/monarch-mcp-server">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@robcerda/monarch-mcp-server/badge" alt="monarch-mcp-server MCP server" />
</a>

## 🚀 Quick Start

### 1. Installation

1. **Clone this repository**:
   ```bash
   git clone https://github.com/robcerda/monarch-mcp-server.git
   cd monarch-mcp-server
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

3. **Configure Claude Desktop**:
   Add this to your Claude Desktop configuration file:
   
   **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   
   **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   
   ```json
   {
     "mcpServers": {
       "Monarch Money": {
         "command": "/opt/homebrew/bin/uv",
         "args": [
           "run",
           "--with",
           "mcp[cli]",
           "--with-editable",
           "/path/to/your/monarch-mcp-server",
           "mcp",
           "run",
           "/path/to/your/monarch-mcp-server/src/monarch_mcp_server/server.py"
         ]
       }
     }
   }
   ```
   
   **Important**: Replace `/path/to/your/monarch-mcp-server` with your actual path!

4. **Restart Claude Desktop**

### 2. One-Time Authentication Setup

**Important**: For security and MFA support, authentication is done outside of Claude Desktop.

Open Terminal and run:
```bash
cd /path/to/your/monarch-mcp-server
python login_setup.py
```

Follow the prompts:
- Enter your Monarch Money email and password
- Provide 2FA code if you have MFA enabled
- Session will be saved automatically

### 3. Start Using in Claude Desktop

Once authenticated, use these tools directly in Claude Desktop:
- `get_accounts` - View all your financial accounts
- `get_transactions` - Recent transactions with filtering
- `get_budgets` - Budget information and spending
- `get_cashflow` - Income/expense analysis

## ✨ Features

### 📊 Account Management
- **Get Accounts**: View all linked financial accounts with balances and institution info
- **Get Account Holdings**: See securities and investments in investment accounts
- **Account History**: Track daily account balance history over time
- **Account Types**: Discover all available account types and subtypes
- **Manual Accounts**: Create, update, and delete manual accounts
- **Refresh Accounts**: Request real-time data updates from financial institutions (blocking and non-blocking)
- **Refresh Status**: Monitor account synchronization progress

### 💰 Transaction Management
- **Get Transactions**: Fetch transaction data with filtering by date, account, and pagination
- **Transaction Details**: View detailed information about specific transactions
- **Transaction Splits**: Manage split transactions across multiple categories
- **Recurring Transactions**: View all recurring transactions with merchant details
- **Transaction Summaries**: Get aggregated transaction data
- **Create Transaction**: Add new transactions to accounts
- **Update Transaction**: Modify existing transactions (amount, description, category, date)
- **Delete Transaction**: Remove transactions from your accounts

### 🏷️ Categories & Tags
- **Get Categories**: View all transaction categories and category groups
- **Create Categories**: Add new custom categories to organize transactions
- **Delete Categories**: Remove single or multiple categories
- **Get Tags**: View all transaction tags
- **Create Tags**: Add new tags with custom colors
- **Assign Tags**: Tag transactions for better organization

### 📈 Budgets & Analytics
- **Get Budgets**: Access budget information including spent amounts and remaining balances
- **Set Budgets**: Create or update budget amounts for categories (set to 0 to clear)
- **Get Cashflow**: Analyze financial cashflow over specified date ranges with income/expense breakdowns
- **Cashflow Summary**: Get aggregated cashflow insights

### 🏦 Institutions & Subscriptions
- **Get Institutions**: View all linked financial institutions
- **Subscription Details**: Check your Monarch Money account status (paid/trial)

### 📊 Data Import
- **Upload Balance History**: Import historical account balance data from CSV files

### 🔐 Secure Authentication
- **One-Time Setup**: Authenticate once, use for weeks/months
- **MFA Support**: Full support for two-factor authentication
- **Session Persistence**: No need to re-authenticate frequently
- **Secure**: Credentials never pass through Claude Desktop

### 🛡️ Safety Features (NEW!)
- **User Approval System**: Destructive operations require explicit approval (like Claude Code commands)
- **Emergency Stop**: Instantly disable all write operations if needed
- **Operation Audit Log**: Track all write operations with timestamps
- **Configurable Protection**: Customize which operations require approval
- **No Runaway Risk**: Claude cannot delete/modify data without your approval

## 🛠️ Available Tools

### Core Tools
| Tool | Description | Parameters |
|------|-------------|------------|
| `setup_authentication` | Get setup instructions | None |
| `check_auth_status` | Check authentication status | None |

### Account Management
| Tool | Description | Parameters |
|------|-------------|------------|
| `get_accounts` | Get all financial accounts | None |
| `get_account_holdings` | Get investment holdings | `account_id` |
| `get_account_history` | Get daily account balance history | `account_id`, `start_date`, `end_date` |
| `get_account_type_options` | Get all available account types and subtypes | None |
| `create_manual_account` | Create a manual account | `account_name`, `account_type`, `current_balance`, `account_subtype` |
| `update_account` | Update account settings or balance | `account_id`, `name`, `balance`, `account_type` |
| `delete_account` | Delete an account ⚠️ REQUIRES APPROVAL | `account_id` |
| `refresh_accounts` | Request account data refresh (non-blocking) | None |
| `request_accounts_refresh_and_wait` | Request account refresh and wait for completion | None |
| `is_accounts_refresh_complete` | Check if account refresh is complete | None |

### Transactions
| Tool | Description | Parameters |
|------|-------------|------------|
| `get_transactions` | Get transactions with filtering | `limit`, `offset`, `start_date`, `end_date`, `account_id` |
| `get_transaction_details` | Get detailed info about a specific transaction | `transaction_id` |
| `get_transaction_splits` | Get split information for a transaction | `transaction_id` |
| `get_transactions_summary` | Get aggregated transaction summary | `start_date`, `end_date` |
| `get_recurring_transactions` | Get all recurring transactions | None |
| `create_transaction` | Create new transaction | `account_id`, `amount`, `description`, `date`, `category_id`, `merchant_name` |
| `update_transaction` | Update existing transaction | `transaction_id`, `amount`, `description`, `category_id`, `date` |
| `update_transaction_splits` | Update or create transaction splits | `transaction_id`, `splits_data` |
| `delete_transaction` | Delete a transaction ⚠️ REQUIRES APPROVAL | `transaction_id` |

### Categories & Tags
| Tool | Description | Parameters |
|------|-------------|------------|
| `get_transaction_categories` | Get all transaction categories | None |
| `get_transaction_category_groups` | Get all category groups | None |
| `create_transaction_category` | Create a new category | `name`, `group_id` |
| `delete_transaction_category` | Delete a category ⚠️ REQUIRES APPROVAL | `category_id` |
| `delete_transaction_categories` | Delete multiple categories ⚠️ REQUIRES APPROVAL | `category_ids` (comma-separated) |
| `get_transaction_tags` | Get all transaction tags | None |
| `create_tag` | Create a new tag | `name`, `color` |
| `set_transaction_tags` | Assign tags to a transaction | `transaction_id`, `tag_ids` (comma-separated) |

### Budgets & Analytics
| Tool | Description | Parameters |
|------|-------------|------------|
| `get_budgets` | Get budget information | None |
| `set_budget_amount` | Set or update budget amount for a category | `category_id`, `amount` |
| `get_cashflow` | Get cashflow analysis | `start_date`, `end_date` |
| `get_cashflow_summary` | Get aggregated cashflow summary | `start_date`, `end_date` |

### Safety & Monitoring
| Tool | Description | Parameters |
|------|-------------|------------|
| `get_safety_stats` | View operation statistics and safety status | None |
| `get_recent_operations` | View recent write operations with rollback info | `limit` (default: 10) |
| `get_rollback_suggestions` | Get detailed rollback instructions for an operation | `operation_index` (0 = most recent) |
| `enable_emergency_stop` | Block ALL write operations immediately | None |
| `disable_emergency_stop` | Re-enable write operations | None |

### Other
| Tool | Description | Parameters |
|------|-------------|------------|
| `get_institutions` | Get all linked financial institutions | None |
| `get_subscription_details` | Get subscription info (paid/trial status) | None |
| `upload_account_balance_history` | Upload account balance history from CSV ⚠️ REQUIRES APPROVAL | `account_id`, `csv_data` |

## 📝 Usage Examples

### Account Management
```
# View all accounts
Use get_accounts to show me all my financial accounts

# Track account balance history
Show me the balance history for account ABC123 for the last 30 days

# Create a manual account
Create a manual savings account called "Emergency Fund" with a balance of $5000

# Update an account
Update account ABC123 to rename it to "Primary Checking"
```

### Transaction Management
```
# Get recent transactions
Show me my last 50 transactions using get_transactions with limit 50

# View transaction details
Get detailed information about transaction XYZ789

# Create a split transaction
Split transaction XYZ789: $50 to groceries and $30 to dining

# Tag transactions
Tag transaction XYZ789 with tags for "vacation" and "reimbursable"

# Delete a transaction
Delete transaction XYZ789
```

### Categories & Tags
```
# View all categories
Show me all my transaction categories

# Create a new category
Create a new category called "Subscriptions" in the Bills category group

# Create tags
Create a new tag called "Tax Deductible" with color #FF5733

# Delete categories
Delete category ABC123
```

### Budgets & Analytics
```
# Check spending vs budget
Use get_budgets to show my current budget status

# Set a budget
Set a budget of $500 for the Groceries category

# Analyze cash flow
Get my cashflow for the last 3 months using get_cashflow

# View cashflow summary
Show me a summary of my income and expenses for this year
```

### Advanced Features
```
# View recurring transactions
Show me all my recurring transactions

# Check account refresh status
Is my account refresh complete?

# Upload balance history
Upload historical balance data for account ABC123 from a CSV file

# Check subscription status
What's my Monarch Money subscription status?
```

## 🛡️ Safety & Protection

This extended version includes comprehensive safety features to protect your financial data:

### User Approval for Destructive Operations

Operations marked with ⚠️ REQUIRES APPROVAL will prompt you for confirmation before executing:

- **delete_transaction** - Prevents accidental transaction deletion
- **delete_account** - Protects against account removal
- **delete_transaction_category** - Safeguards category structure
- **delete_transaction_categories** - Extra protection for bulk deletes
- **upload_account_balance_history** - Prevents accidental data overwrites

### Safety Tools

```
# Monitor today's operations
get_safety_stats

# View recent operations with rollback info
get_recent_operations(limit=10)

# Get rollback instructions for most recent operation
get_rollback_suggestions(operation_index=0)

# Emergency controls
enable_emergency_stop    # Block ALL write operations immediately
disable_emergency_stop   # Resume normal operation
```

### How It Works

1. **User Approval**: You must click [Approve] for each destructive operation
2. **Detailed Logging**: Every operation logged with full parameters for rollback
3. **Rollback Support**: View recent operations and get instructions to undo them
4. **Emergency Stop**: Instantly disable all writes if you detect runaway behavior
5. **Audit Trail**: All operations logged to `~/.mm/detailed_operation_log.jsonl`
6. **Configurable**: Customize which operations require approval in `~/.mm/safety_config.json`

**See [SAFETY.md](SAFETY.md) for complete safety documentation.**

## 📅 Date Formats

- All dates should be in `YYYY-MM-DD` format (e.g., "2024-01-15")
- Transaction amounts: **positive** for income, **negative** for expenses

## 🔧 Troubleshooting

### Authentication Issues
If you see "Authentication needed" errors:
1. Run the setup command: `cd /path/to/your/monarch-mcp-server && python login_setup.py`
2. Restart Claude Desktop
3. Try using a tool like `get_accounts`

### Session Expired
Sessions last for weeks, but if expired:
1. Run the same setup command again
2. Enter your credentials and 2FA code
3. Session will be refreshed automatically

### Common Error Messages
- **"No valid session found"**: Run `login_setup.py` 
- **"Invalid account ID"**: Use `get_accounts` to see valid account IDs
- **"Date format error"**: Use YYYY-MM-DD format for dates

## 🏗️ Technical Details

### Project Structure
```
monarch-mcp-server/
├── src/monarch_mcp_server/
│   ├── __init__.py
│   └── server.py          # Main server implementation
├── login_setup.py         # Authentication setup script
├── pyproject.toml         # Project configuration
├── requirements.txt       # Dependencies
└── README.md             # This documentation
```

### Session Management
- Sessions are stored securely in `.mm/mm_session.pickle`
- Automatic session discovery and loading
- Sessions persist across Claude Desktop restarts
- No need for frequent re-authentication

### Security Features
- Credentials never transmitted through Claude Desktop
- MFA/2FA fully supported
- Session files are encrypted
- Authentication handled in secure terminal environment

## 🙏 Acknowledgments

This MCP server is built on top of the excellent [MonarchMoney Python library](https://github.com/hammem/monarchmoney) created by [@hammem](https://github.com/hammem). Their library provides the robust foundation that makes this integration possible, including:

- Secure authentication with MFA support
- Comprehensive API coverage for Monarch Money
- Session management and persistence
- Well-documented and maintained codebase

Thank you to [@hammem](https://github.com/hammem) for creating and maintaining this essential library!

## 📄 License

MIT License

## 🆘 Support

For issues:
1. Check authentication with `check_auth_status`
2. Run the setup command again: `cd /path/to/your/monarch-mcp-server && python login_setup.py`
3. Check error logs for detailed messages
4. Ensure Monarch Money service is accessible

## 🔄 Updates

To update the server:
1. Pull latest changes from repository
2. Restart Claude Desktop
3. Re-run authentication if needed: `python login_setup.py`