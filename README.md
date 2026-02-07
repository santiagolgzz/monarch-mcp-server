# Monarch Money MCP Server

A comprehensive [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for [Monarch Money](https://www.monarchmoney.com/) personal finance. **40+ tools** covering the complete Monarch Money API — works out of the box with Claude Desktop, Claude mobile, or any MCP client.

Built on the [MonarchMoney Python library](https://github.com/hammem/monarchmoney) by [@hammem](https://github.com/hammem).

## ✨ Features

- 📊 **Complete API Coverage** — 40+ tools for accounts, transactions, budgets, categories, tags, and more
- 🌐 **Two Deployment Modes** — Local (stdio) for Claude Desktop, or HTTP/SSE for mobile and remote access
- 🛡️ **Safety First** — Destructive operations require approval, with audit logging and rollback support
- 🔐 **Secure Authentication** — Keyring integration, MFA support, long-lived sessions
- ✅ **Production Ready** — 90%+ test coverage, CI/CD pipelines, Docker support

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/santiagolgzz/monarch-mcp-server.git
cd monarch-mcp-server
pip install -e .
```

### 2. Authentication

**Option A: Interactive Login (Recommended)**

Run once to save session to your system keyring:
```bash
python login_setup.py
```

Sessions are stored securely in your OS keyring (macOS Keychain, Windows Credential Manager, etc.) and persist for weeks.

**Option B: Environment Variables**

For CI/CD or containerized deployments where keyring isn't available:
```bash
export MONARCH_EMAIL="your@email.com"
export MONARCH_PASSWORD="your_password"
export MONARCH_MFA_SECRET="your_totp_secret"  # Optional, for auto-MFA
```

⚠️ Use secrets management (Docker secrets, Cloud Run secrets, etc.) rather than plain env vars in production.

### 3. Configure Claude Desktop

Add to your Claude Desktop config:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "monarch-money": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/monarch-mcp-server", "monarch-mcp"]
    }
  }
}
```

**Important**: Replace `/path/to/monarch-mcp-server` with your actual path!

### 4. Restart Claude Desktop

Start using Monarch Money tools immediately.

### 📱 Claude Mobile / Remote Access

For mobile or remote deployment, see **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for HTTP/SSE setup.
Default remote auth mode is now single-user token auth (`MCP_AUTH_MODE=token`), with GitHub OAuth available as an advanced option (`MCP_AUTH_MODE=oauth`).

## 🛠️ Available Tools

| Category | Count | Tools |
|----------|-------|-------|
| **Accounts** | 10 | `get_accounts`, `get_account_holdings`, `get_account_history`, `create_manual_account`, `update_account`, `delete_account`, `upload_account_balance_history` |
| **Transactions** | 12 | `get_transactions`, `get_transaction_details`, `search_transactions`, `get_transaction_stats`, `create_transaction`, `update_transaction`, `delete_transaction`, `get_transaction_splits`, `update_transaction_splits` |
| **Categories** | 6 | `get_transaction_categories`, `get_transaction_category_groups`, `create_transaction_category`, `delete_transaction_category`, `delete_transaction_categories` |
| **Tags** | 3 | `get_transaction_tags`, `create_tag`, `set_transaction_tags` |
| **Budgets** | 2 | `get_budgets`, `set_budget_amount` |
| **Safety** | 5 | `get_safety_stats`, `get_recent_operations`, `get_rollback_suggestions`, `enable_emergency_stop`, `disable_emergency_stop` |
| **Metadata** | 5 | `get_subscription_details`, `get_institutions`, `refresh_accounts`, `is_accounts_refresh_complete`, `request_accounts_refresh_and_wait` |

**[📖 See docs/TOOLS.md for complete tool reference with parameters](docs/TOOLS.md)**

## 📝 Usage Examples

### View Your Accounts
```
Show me all my financial accounts and their balances
```

### Get Recent Transactions
```
Show my last 50 transactions from my Chase checking account
```

### Search Transactions
```
Find all transactions from Amazon in the last 3 months
```

### Check Budget Status
```
How am I doing on my budgets this month?
```

### Analyze Spending
```
What were my top spending categories last month?
```

### Create a Transaction
```
Add a $50 transaction at Whole Foods on my Chase card, category Groceries, dated today
```

### Track Account History
```
Show my checking account balance history for the past 90 days
```

## 📅 Date Formats

- All dates use `YYYY-MM-DD` format (e.g., "2024-01-15")
- Transaction amounts: **positive** for income, **negative** for expenses

## 🛡️ Safety Features

Destructive operations require explicit approval:

| Operation | Protection |
|-----------|------------|
| `delete_transaction` | Requires confirmation |
| `delete_account` | Requires confirmation |
| `delete_transaction_category` | Requires confirmation |
| `upload_account_balance_history` | Prevents accidental overwrites |

### Safety Tools

| Tool | Description |
|------|-------------|
| `get_safety_stats` | View today's operation counts |
| `get_recent_operations` | Review recent write operations |
| `get_rollback_suggestions` | Get instructions to undo an operation |
| `enable_emergency_stop` | Block all writes instantly |
| `disable_emergency_stop` | Re-enable writes after emergency stop |

All write operations are logged to `~/.mm/detailed_operation_log.jsonl` for audit and rollback.

**[📖 See docs/ROLLBACK_GUIDE.md for detailed rollback procedures](docs/ROLLBACK_GUIDE.md)**

## 🔐 Security

- **Credentials never pass through Claude** — authentication happens in your terminal
- **MFA/2FA fully supported** — including TOTP auto-authentication
- **Secure session storage** — uses system keyring (macOS Keychain, Windows Credential Manager, etc.)
- **Sessions persist for weeks** — no frequent re-authentication needed

## 🔧 Troubleshooting

### "No valid session found"
Run `python login_setup.py` to authenticate, or set `MONARCH_EMAIL` and `MONARCH_PASSWORD` environment variables.

### "Session expired"
Sessions last weeks, but if expired, re-run `python login_setup.py`.

### "Invalid account/transaction ID"
Use `get_accounts` or `get_transactions` first to get valid IDs.

### Date format errors
Use `YYYY-MM-DD` format (e.g., "2024-01-15").

### Connection issues
Use `check_auth_status` to verify your connection is working.

## 🏗️ Project Structure

```
monarch-mcp-server/
├── src/monarch_mcp_server/
│   ├── server.py          # MCP server (stdio mode)
│   ├── http_server.py     # HTTP/SSE server (remote mode)
│   ├── client.py          # Monarch Money client
│   ├── tools/             # Modular tool implementations
│   ├── safety.py          # Safety system and audit logging
│   └── secure_session.py  # Keyring-based session management
├── docs/
│   ├── TOOLS.md           # Complete tool reference
│   ├── DEPLOYMENT.md      # Remote deployment guide
│   └── ROLLBACK_GUIDE.md  # Rollback procedures
├── tests/                 # Comprehensive test suite (90%+ coverage)
├── login_setup.py         # Authentication setup script
└── pyproject.toml
```

## 💻 Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Type check
ty check src/

# Lint
ruff check src/ tests/
```

## 🔄 Updates

To update the server:
```bash
git pull
pip install -e .
```

Re-run authentication if needed: `python login_setup.py`

## 📋 Requirements

- Python 3.11+
- Monarch Money account
- Claude Desktop, Claude mobile, or other MCP client

## 📄 License

MIT License

## 🙏 Acknowledgments

- **[@robcerda](https://github.com/robcerda)** — Original MCP server implementation that this project builds upon
- **[@hammem](https://github.com/hammem)** — [MonarchMoney Python library](https://github.com/hammem/monarchmoney) providing the robust API foundation with MFA support and session management
