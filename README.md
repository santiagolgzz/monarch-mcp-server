# Monarch Money MCP Server

A comprehensive [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for [Monarch Money](https://www.monarchmoney.com/) personal finance. **40+ tools** covering the complete Monarch Money API - works out of the box with Claude Desktop, Claude mobile, or any MCP client.

## Features

- **Complete API Coverage** - 40+ tools for accounts, transactions, budgets, categories, tags, and more
- **Two Deployment Modes** - Local (stdio) for Claude Desktop, or HTTP/SSE for mobile and remote access
- **Safety First** - Destructive operations require approval, with audit logging and rollback support
- **Secure Authentication** - Keyring integration, MFA support, long-lived sessions
- **Production Ready** - 90%+ test coverage, CI/CD pipelines, Docker support

## Quick Start

### Claude Desktop (Local)

1. **Clone and install:**
   ```bash
   git clone https://github.com/santiagolgzz/monarch-mcp-server.git
   cd monarch-mcp-server
   pip install -e .
   ```

2. **Authenticate with Monarch Money:**
   ```bash
   python login_setup.py
   ```
   Enter your email, password, and 2FA code if enabled.

3. **Configure Claude Desktop:**

   Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):
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

4. **Restart Claude Desktop** and start using Monarch Money tools.

### Claude Mobile / Remote Access

For mobile or remote deployment, see **[DEPLOYMENT.md](DEPLOYMENT.md)** for HTTP/SSE server setup with GitHub OAuth.

## Authentication

Authentication is done once via terminal for security (credentials never pass through Claude):

```bash
python login_setup.py
```

Sessions are stored securely in your system keyring and persist for weeks. Re-run if your session expires.

## Tools Overview

| Category | Tools | Examples |
|----------|-------|----------|
| **Accounts** | 10 | `get_accounts`, `get_account_history`, `create_manual_account` |
| **Transactions** | 12 | `get_transactions`, `search_transactions`, `create_transaction` |
| **Categories & Tags** | 9 | `get_transaction_categories`, `create_tag`, `set_transaction_tags` |
| **Budgets** | 4 | `get_budgets`, `set_budget_amount`, `get_cashflow` |
| **Safety** | 5 | `get_safety_stats`, `enable_emergency_stop`, `get_rollback_suggestions` |
| **Other** | 3 | `get_institutions`, `get_subscription_details` |

**[See TOOLS.md for complete tool reference](TOOLS.md)**

### Example Prompts

```
Show me all my accounts and their balances

What were my top spending categories last month?

Create a new transaction: $50 at Whole Foods on my Chase card, category Groceries

Show my budget status for this month

Track my checking account balance history for the past 90 days
```

## Safety Features

Destructive operations (delete, bulk updates) require explicit approval:

- **delete_transaction**, **delete_account**, **delete_transaction_category** - prompt before executing
- **upload_account_balance_history** - prevents accidental data overwrites

### Safety Tools

- `get_safety_stats` - View today's operation counts
- `get_recent_operations` - Review recent write operations
- `get_rollback_suggestions` - Get instructions to undo an operation
- `enable_emergency_stop` / `disable_emergency_stop` - Block all writes instantly

All write operations are logged to `~/.mm/detailed_operation_log.jsonl` for audit and rollback.

**[See ROLLBACK_GUIDE.md for detailed rollback procedures](ROLLBACK_GUIDE.md)**

## Project Structure

```
monarch-mcp-server/
├── src/monarch_mcp_server/
│   ├── server.py          # MCP server (stdio mode)
│   ├── http_server.py     # HTTP/SSE server (remote mode)
│   ├── client.py          # Monarch Money client initialization
│   ├── tools/             # Modular tool implementations
│   │   ├── accounts.py
│   │   ├── transactions.py
│   │   ├── categories.py
│   │   ├── budgets.py
│   │   └── ...
│   ├── safety.py          # Safety system and audit logging
│   └── secure_session.py  # Keyring-based session management
├── tests/                 # Comprehensive test suite
├── login_setup.py         # Authentication setup script
└── pyproject.toml
```

## Requirements

- Python 3.11+
- Monarch Money account
- Claude Desktop, Claude mobile, or other MCP client

## Troubleshooting

### "No valid session found"
Run `python login_setup.py` to authenticate.

### "Session expired"
Sessions last weeks, but if expired, re-run `python login_setup.py`.

### "Invalid account/transaction ID"
Use `get_accounts` or `get_transactions` first to get valid IDs.

### Date format errors
Use `YYYY-MM-DD` format (e.g., "2024-01-15").

## Development

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

## License

MIT License

## Acknowledgments

Built on the [MonarchMoney Python library](https://github.com/hammem/monarchmoney) by [@hammem](https://github.com/hammem).
