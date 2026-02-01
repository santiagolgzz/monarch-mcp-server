"""
HTTP server with GitHub OAuth for Monarch Money MCP Server.

This module enables hosting the MCP server online for use with Claude mobile app
and other remote MCP clients. It wraps the server with:
- GitHub OAuth authentication (RFC-compliant)
- SSE/Streamable HTTP transport for MCP protocol
- Health check endpoint for monitoring

Usage:
    # Set required environment variables:
    export GITHUB_CLIENT_ID="your-github-client-id"
    export GITHUB_CLIENT_SECRET="your-github-client-secret"
    export MONARCH_TOKEN="your-monarch-token"  # From login_setup.py

    # Run the server:
    python -m monarch_mcp_server.http_server

    # Or with uvicorn directly:
    uvicorn monarch_mcp_server.http_server:app --host 0.0.0.0 --port 8000
"""

import os
import logging
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, Mount

from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_base_url() -> str:
    """Get the base URL for the server."""
    # Allow explicit override
    if base_url := os.getenv("BASE_URL"):
        return base_url.rstrip("/")

    # Railway sets PORT and provides a domain
    port = os.getenv("PORT", "8000")

    # Check for Railway's automatic domain
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if railway_domain:
        return f"https://{railway_domain}"

    # Check for Google Cloud Run
    cloud_run_service = os.getenv("K_SERVICE")
    cloud_run_region = os.getenv("CLOUD_RUN_REGION", "us-central1")
    gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    if cloud_run_service and gcp_project:
        return f"https://{cloud_run_service}-{gcp_project}.{cloud_run_region}.run.app"

    # Local development
    host = os.getenv("HOST", "localhost")
    return f"http://{host}:{port}"


def create_mcp_server() -> FastMCP:
    """Create the FastMCP server with GitHub OAuth and all Monarch tools."""

    base_url = get_base_url()
    client_id = os.getenv("GITHUB_CLIENT_ID", "")
    client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        logger.warning("GitHub OAuth credentials not set - server will fail auth requests")

    # Create GitHub OAuth provider
    github_auth = GitHubProvider(
        client_id=client_id,
        client_secret=client_secret,
        base_url=base_url,
        redirect_path="/auth/callback",
        # Don't require consent screen for personal use
        require_authorization_consent=False,
    )

    # Create FastMCP server with auth
    mcp = FastMCP(
        "Monarch Money MCP Server",
        auth=github_auth,
        instructions="MCP server for Monarch Money personal finance management",
    )

    # Import and register all tools from the original server
    _register_monarch_tools(mcp)

    return mcp


def _register_monarch_tools(mcp: FastMCP) -> None:
    """Register all Monarch Money tools with the FastMCP server."""

    # Import dependencies
    import json
    from monarch_mcp_server.secure_session import secure_session
    from monarch_mcp_server.safety import get_safety_guard, require_safety_check
    from monarch_mcp_server.utils import (
        run_async,
        format_error,
        validate_date_format,
        validate_non_empty_string,
    )
    from monarch_mcp_server.exceptions import ValidationError
    from monarchmoney import MonarchMoney, MonarchMoneyEndpoints

    # Apply the API URL patch
    MonarchMoneyEndpoints.BASE_URL = "https://api.monarch.com"

    async def get_monarch_client() -> MonarchMoney:
        """Get or create MonarchMoney client instance."""
        client = secure_session.get_authenticated_client()
        if client is not None:
            return client

        email = os.getenv("MONARCH_EMAIL")
        password = os.getenv("MONARCH_PASSWORD")

        if email and password:
            client = MonarchMoney()
            mfa_secret = os.getenv("MONARCH_MFA_SECRET")
            await client.login(email, password, mfa_secret_key=mfa_secret)
            secure_session.save_authenticated_session(client)
            return client

        raise RuntimeError("Authentication needed! Set MONARCH_TOKEN env var.")

    # ========== READ-ONLY TOOLS ==========

    @mcp.tool()
    def get_accounts() -> str:
        """Get all financial accounts from Monarch Money."""
        try:
            async def _get_accounts():
                client = await get_monarch_client()
                return await client.get_accounts()

            accounts = run_async(_get_accounts())
            account_list = []
            for account in accounts.get("accounts", []):
                account_info = {
                    "id": account.get("id"),
                    "name": account.get("displayName") or account.get("name"),
                    "type": (account.get("type") or {}).get("name"),
                    "balance": account.get("currentBalance"),
                    "institution": (account.get("institution") or {}).get("name"),
                    "is_active": account.get("isActive") if "isActive" in account else not account.get("deactivatedAt"),
                }
                account_list.append(account_info)
            return json.dumps(account_list, indent=2, default=str)
        except Exception as e:
            return format_error(e, "get_accounts")

    @mcp.tool()
    def get_transactions(
        limit: int = 100,
        offset: int = 0,
        start_date: str | None = None,
        end_date: str | None = None,
        account_id: str | None = None,
    ) -> str:
        """Get transactions from Monarch Money."""
        try:
            validated_start = validate_date_format(start_date, "start_date")
            validated_end = validate_date_format(end_date, "end_date")

            async def _get_transactions():
                client = await get_monarch_client()
                filters = {}
                if validated_start:
                    filters["start_date"] = validated_start
                if validated_end:
                    filters["end_date"] = validated_end
                if account_id:
                    filters["account_id"] = account_id
                return await client.get_transactions(limit=limit, offset=offset, **filters)

            transactions = run_async(_get_transactions())
            transaction_list = []
            for txn in transactions.get("allTransactions", {}).get("results", []):
                transaction_info = {
                    "id": txn.get("id"),
                    "date": txn.get("date"),
                    "amount": txn.get("amount"),
                    "description": txn.get("description"),
                    "category": txn.get("category", {}).get("name") if txn.get("category") else None,
                    "account": txn.get("account", {}).get("displayName"),
                    "merchant": txn.get("merchant", {}).get("name") if txn.get("merchant") else None,
                    "is_pending": txn.get("isPending", False),
                }
                transaction_list.append(transaction_info)
            return json.dumps(transaction_list, indent=2, default=str)
        except Exception as e:
            return format_error(e, "get_transactions")

    @mcp.tool()
    def get_budgets() -> str:
        """Get budget information from Monarch Money."""
        try:
            async def _get_budgets():
                client = await get_monarch_client()
                return await client.get_budgets()

            budgets = run_async(_get_budgets())
            budget_list = []
            for budget in budgets.get("budgets", []):
                budget_info = {
                    "id": budget.get("id"),
                    "name": budget.get("name"),
                    "amount": budget.get("amount"),
                    "spent": budget.get("spent"),
                    "remaining": budget.get("remaining"),
                    "category": budget.get("category", {}).get("name"),
                    "period": budget.get("period"),
                }
                budget_list.append(budget_info)
            return json.dumps(budget_list, indent=2, default=str)
        except Exception as e:
            return f"Error getting budgets: {str(e)}"

    @mcp.tool()
    def get_transaction_categories() -> str:
        """Get all transaction categories from Monarch Money with their IDs."""
        try:
            async def _get_categories():
                client = await get_monarch_client()
                return await client.get_transaction_categories()

            categories = run_async(_get_categories())
            category_list = []
            for cat in categories.get("categories", []):
                category_info = {
                    "id": cat.get("id"),
                    "name": cat.get("name"),
                    "icon": cat.get("icon"),
                    "group": cat.get("group", {}).get("name") if cat.get("group") else None,
                }
                category_list.append(category_info)
            return json.dumps(category_list, indent=2, default=str)
        except Exception as e:
            return f"Error getting transaction categories: {str(e)}"

    @mcp.tool()
    def get_cashflow(start_date: str | None = None, end_date: str | None = None) -> str:
        """Get cashflow analysis from Monarch Money."""
        try:
            async def _get_cashflow():
                client = await get_monarch_client()
                filters = {}
                if start_date:
                    filters["start_date"] = start_date
                if end_date:
                    filters["end_date"] = end_date
                return await client.get_cashflow(**filters)

            cashflow = run_async(_get_cashflow())
            return json.dumps(cashflow, indent=2, default=str)
        except Exception as e:
            return f"Error getting cashflow: {str(e)}"

    @mcp.tool()
    def get_subscription_details() -> str:
        """Get Monarch Money subscription details (account status, paid/trial)."""
        try:
            async def _get_subscription():
                client = await get_monarch_client()
                return await client.get_subscription_details()

            subscription = run_async(_get_subscription())
            return json.dumps(subscription, indent=2, default=str)
        except Exception as e:
            return f"Error getting subscription details: {str(e)}"

    # ========== SAFETY TOOLS ==========

    @mcp.tool()
    def get_safety_stats() -> str:
        """Get current safety statistics including rate limits and daily operation counts."""
        try:
            guard = get_safety_guard()
            stats = guard.get_operation_stats()
            return json.dumps(stats, indent=2, default=str)
        except Exception as e:
            return f"Error getting safety stats: {str(e)}"

    logger.info("Registered Monarch Money tools with FastMCP server")


# Health check endpoint (public, no auth required)
async def health_check(request: Request) -> Response:
    """Health check endpoint for monitoring and load balancers."""
    from monarch_mcp_server.secure_session import secure_session

    has_credentials = (
        bool(os.getenv("MONARCH_TOKEN")) or
        (bool(os.getenv("MONARCH_EMAIL")) and bool(os.getenv("MONARCH_PASSWORD"))) or
        secure_session.load_token() is not None
    )
    has_github_oauth = bool(os.getenv("GITHUB_CLIENT_ID"))

    status = {
        "status": "healthy",
        "service": "monarch-mcp-server",
        "has_monarch_credentials": has_credentials,
        "github_oauth_configured": has_github_oauth,
        "base_url": get_base_url(),
    }

    return JSONResponse(status)


async def root(request: Request) -> Response:
    """Root endpoint with basic info."""
    base_url = get_base_url()
    return JSONResponse({
        "service": "Monarch Money MCP Server",
        "description": "MCP server for Monarch Money personal finance",
        "endpoints": {
            "/health": "Health check endpoint (public)",
            "/mcp": "MCP endpoint (requires GitHub OAuth)",
            "/.well-known/oauth-authorization-server": "OAuth discovery endpoint",
        },
        "auth": "GitHub OAuth - configure in Claude mobile app with OAuth client ID",
        "oauth_discovery": f"{base_url}/.well-known/oauth-authorization-server",
    })


def create_app() -> Starlette:
    """Create the Starlette ASGI application."""
    mcp_server = create_mcp_server()

    # Get the HTTP app from FastMCP (includes OAuth routes)
    mcp_app = mcp_server.http_app(path="/mcp")

    # Get well-known routes for OAuth discovery
    if mcp_server.auth:
        well_known_routes = mcp_server.auth.get_well_known_routes(mcp_path="/mcp")
    else:
        well_known_routes = []

    # Create main app combining everything
    app = Starlette(
        debug=os.getenv("DEBUG", "false").lower() == "true",
        routes=[
            Route("/", root),
            Route("/health", health_check),
            # Well-known routes at root for OAuth discovery
            *well_known_routes,
            # Mount the MCP app
            Mount("/", app=mcp_app),
        ],
        lifespan=mcp_app.lifespan,
    )

    logger.info("Monarch Money MCP HTTP Server with GitHub OAuth initialized")

    return app


# Create the ASGI app instance
app = create_app()


def main():
    """Run the HTTP server using uvicorn."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    # Validate configuration
    if not os.getenv("GITHUB_CLIENT_ID") or not os.getenv("GITHUB_CLIENT_SECRET"):
        logger.error("=" * 60)
        logger.error("ERROR: GitHub OAuth credentials required!")
        logger.error("Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET")
        logger.error("=" * 60)
        raise SystemExit(1)

    if not os.getenv("MONARCH_TOKEN"):
        logger.warning("=" * 60)
        logger.warning("WARNING: MONARCH_TOKEN not set")
        logger.warning("Run 'python login_setup.py' locally, then copy the token")
        logger.warning("=" * 60)

    base_url = get_base_url()
    logger.info(f"Starting Monarch Money MCP Server on {base_url}")
    logger.info(f"MCP endpoint: {base_url}/mcp")
    logger.info(f"OAuth discovery: {base_url}/.well-known/oauth-authorization-server")
    logger.info(f"Health check: {base_url}/health")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
