"""Monarch Money MCP Server - Main server implementation."""

import logging

from dotenv import load_dotenv
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP(
    "Monarch Money MCP Server",
    instructions="MCP server for Monarch Money personal finance management",
)

# Register all shared tools
register_tools(mcp)


@mcp.tool()
def setup_authentication() -> str:
    """Get instructions for setting up authentication with Monarch Money."""
    return """🔐 Monarch Money Authentication

Option 1: Interactive Login (Recommended)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run once to save session to your OS keyring:

  python login_setup.py

Session is stored securely (macOS Keychain, Windows Credential
Manager, etc.) and persists for weeks across restarts.

Option 2: Environment Variables
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For CI/CD or containers where keyring isn't available:

  MONARCH_EMAIL=your@email.com
  MONARCH_PASSWORD=your_password
  MONARCH_MFA_SECRET=your_totp_secret  # Optional

⚠️  Use secrets management in production, not plain env vars.

Use check_auth_status to verify your connection."""


@mcp.tool()
async def check_auth_status() -> str:
    """Check if already authenticated with Monarch Money.

    Verifies the connection by making a lightweight API call to Monarch's servers.
    Works for both local (keyring) and remote (env var) authentication modes.
    """
    try:
        from monarch_mcp_server.client import get_monarch_client

        # Try to get an authenticated client and verify it works
        client = await get_monarch_client()
        subscription = await client.get_subscription_details()

        # Extract useful info from subscription
        is_paid = subscription.get("hasPremiumEntitlement", False)
        plan_type = "Premium" if is_paid else "Free/Trial"

        return f"✅ Authenticated and connected to Monarch Money\n📊 Plan: {plan_type}"

    except Exception as e:
        error_msg = str(e)
        if "Authentication required" in error_msg:
            return (
                "❌ Not authenticated\n\n"
                "For local use: Run `python login_setup.py`\n"
                "For remote use: Set MONARCH_EMAIL and MONARCH_PASSWORD env vars"
            )
        return f"⚠️ Connection failed: {error_msg}"


def main():
    """Main entry point for the server."""
    logger.info("Starting Monarch Money MCP Server...")
    try:
        # Stdio MCP servers must keep stdout clean for JSON-RPC frames.
        mcp.run(show_banner=False)
    except Exception as e:
        logger.error(f"Failed to run server: {str(e)}")
        raise


# Export for mcp run
app = mcp

if __name__ == "__main__":
    main()
