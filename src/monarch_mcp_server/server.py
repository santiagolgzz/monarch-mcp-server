"""Monarch Money MCP Server - Main server implementation.
"""

import logging
import os

from dotenv import load_dotenv
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
    """Get instructions for setting up secure authentication with Monarch Money."""
    return """🔐 Monarch Money - One-Time Setup

1️⃣ Open Terminal and run:
   python login_setup.py

2️⃣ Enter your Monarch Money credentials when prompted
   • Email and password
   • 2FA code if you have MFA enabled

3️⃣ Session will be saved automatically and last for weeks

4️⃣ Start using Monarch tools in Claude Desktop:
   • get_accounts - View all accounts
   • get_transactions - Recent transactions
   • get_budgets - Budget information

✅ Session persists across Claude restarts
✅ No need to re-authenticate frequently
✅ All credentials stay secure in terminal"""


@mcp.tool()
def check_auth_status() -> str:
    """Check if already authenticated with Monarch Money."""
    try:
        from monarch_mcp_server.secure_session import secure_session
        # Check if we have a token in the keyring
        token = secure_session.load_token()
        if token:
            status = "✅ Authentication token found in secure keyring storage\n"
        else:
            status = "❌ No authentication token found in keyring\n"

        email = os.getenv("MONARCH_EMAIL")
        if email:
            status += f"📧 Environment email: {email}\n"

        status += (
            "\n💡 Try get_accounts to test connection or run login_setup.py if needed."
        )

        return status
    except Exception as e:
        return f"Error checking auth status: {str(e)}"


def main():
    """Main entry point for the server."""
    logger.info("Starting Monarch Money MCP Server...")
    try:
        mcp.run()
    except Exception as e:
        logger.error(f"Failed to run server: {str(e)}")
        raise


# Export for mcp run
app = mcp

if __name__ == "__main__":
    main()