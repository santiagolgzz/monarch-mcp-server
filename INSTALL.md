# Installation Guide - Monarch Money MCP Server Extended

## Prerequisites

- Python 3.12 or higher
- Claude Desktop installed
- Monarch Money account
- `uv` package manager (recommended) or `pip`

## Step 1: Clone the Repository

```bash
# Navigate to your desired directory
cd ~

# Clone this repository
git clone <your-fork-url> monarch-mcp-server-extended
cd monarch-mcp-server-extended
```

## Step 2: Install Dependencies

### Option A: Using pip (Recommended for most users)
```bash
pip install -r requirements.txt
pip install -e .
```

### Option B: Using uv (Faster)
```bash
uv pip install -r requirements.txt
uv pip install -e .
```

## Step 3: Configure Claude Desktop

### macOS
Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "Monarch Money Extended": {
      "command": "/opt/homebrew/bin/uv",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "--with-editable",
        "/Users/YOUR_USERNAME/monarch-mcp-server-extended",
        "mcp",
        "run",
        "/Users/YOUR_USERNAME/monarch-mcp-server-extended/src/monarch_mcp_server/server.py"
      ]
    }
  }
}
```

### Windows
Edit: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "Monarch Money Extended": {
      "command": "C:\\Users\\YOUR_USERNAME\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
      "args": [
        "-m",
        "mcp",
        "run",
        "C:\\Users\\YOUR_USERNAME\\monarch-mcp-server-extended\\src\\monarch_mcp_server\\server.py"
      ]
    }
  }
}
```

**Important**: Replace `YOUR_USERNAME` with your actual username and adjust paths as needed.

### Finding Your Python Path

**macOS/Linux**:
```bash
which python3
which uv
```

**Windows**:
```bash
where python
```

## Step 4: Authenticate with Monarch Money

```bash
# Navigate to the project directory
cd monarch-mcp-server-extended

# Run the authentication setup
python login_setup.py
```

Follow the prompts:
1. Enter your Monarch Money email
2. Enter your password
3. If you have MFA/2FA enabled, enter the code when prompted
4. Session will be saved securely

## Step 5: Restart Claude Desktop

1. Quit Claude Desktop completely
2. Reopen Claude Desktop
3. The MCP server should connect automatically

## Step 6: Verify Installation

In Claude Desktop, try these commands:

```
Use check_auth_status to verify I'm connected to Monarch Money

Show me all my accounts using get_accounts

How many tools are available from the Monarch Money server?
```

You should see:
- Authentication confirmed
- Your financial accounts listed
- 37+ tools available (40 including debug tools)

## Troubleshooting

### Authentication Issues

**Problem**: "Authentication needed" error

**Solution**:
```bash
cd monarch-mcp-server-extended
python login_setup.py
```

### Session Expired

**Problem**: Tools stop working after a few weeks

**Solution**: Re-run authentication
```bash
python login_setup.py
```

### Claude Desktop Not Finding Server

**Problem**: MCP server not appearing in Claude Desktop

**Solutions**:
1. Check the config file path is correct
2. Verify all paths in the JSON are absolute paths
3. Check Python/uv is installed and in PATH
4. Restart Claude Desktop
5. Check Claude Desktop logs for errors

**View logs**:
- macOS: `~/Library/Logs/Claude/`
- Windows: `%APPDATA%\Claude\logs\`

### Import Errors

**Problem**: `ModuleNotFoundError` when starting

**Solution**: Reinstall dependencies
```bash
pip install -r requirements.txt
pip install -e .
```

### Python Version Issues

**Problem**: Syntax errors or compatibility issues

**Solution**: Ensure Python 3.12+
```bash
python --version  # Should show 3.12 or higher
```

## Upgrading from Original Version

If you're currently using the original monarch-mcp-server:

1. **Backup** your current config
2. **Install** this extended version alongside (different directory)
3. **Update** your `claude_desktop_config.json` to point to new directory
4. **No need to re-authenticate** - sessions are compatible
5. **Restart** Claude Desktop

All your existing workflows will continue to work, plus you'll have 27+ new tools available!

## Verifying All Features Work

Try each category:

```
# Account management
get_account_type_options
create_manual_account with name "Test Account"

# Categories and tags
get_transaction_categories
create_tag with name "Test Tag"

# Budgets
get_budgets
set_budget_amount for a category

# Analytics
get_cashflow_summary for this month
get_recurring_transactions

# History
get_account_history for one of my accounts
```

## Getting Help

1. Check `TOOLS_REFERENCE.md` for a quick tool overview
2. Check `FEATURES_COMPARISON.md` for what's new
3. Check `README.md` for detailed usage examples
4. Check the original repo issues: https://github.com/robcerda/monarch-mcp-server/issues

## Next Steps

- Read `TOOLS_REFERENCE.md` for a complete list of tools
- Try the examples in `README.md`
- Set up budgets and tags for better organization
- Import historical balance data if needed

Enjoy your enhanced Monarch Money integration! 🎉
