"""
HTTP server with GitHub OAuth for Monarch Money MCP Server.

This module enables hosting the MCP server online for use with Claude mobile app
and other remote MCP clients. It wraps the server with:
- GitHub OAuth authentication (RFC-compliant)
- SSE/Streamable HTTP transport for MCP protocol
- Health check endpoint for monitoring
"""

import logging
import os

import uvicorn
from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from monarch_mcp_server.tools import register_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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

    # Local development
    host = os.getenv("HOST", "localhost")
    return f"http://{host}:{port}"


def create_mcp_server() -> FastMCP:
    """Create the FastMCP server with GitHub OAuth and all Monarch tools."""

    base_url = get_base_url()
    client_id = os.getenv("GITHUB_CLIENT_ID", "")
    client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        logger.error(
            "GitHub OAuth credentials not set - server will fail auth requests"
        )

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

    # Register all shared tools
    register_tools(mcp)

    return mcp


# Health check endpoint (public, no auth required)
async def health_check(request: Request) -> Response:
    """Health check endpoint for monitoring and load balancers."""
    from monarch_mcp_server.secure_session import secure_session

    has_credentials = (
        bool(os.getenv("MONARCH_TOKEN"))
        or (bool(os.getenv("MONARCH_EMAIL")) and bool(os.getenv("MONARCH_PASSWORD")))
        or secure_session.load_token() is not None
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
    return JSONResponse(
        {
            "service": "Monarch Money MCP Server",
            "description": "MCP server for Monarch Money personal finance",
            "endpoints": {
                "/health": "Health check endpoint (public)",
                "/mcp": "MCP endpoint (requires GitHub OAuth)",
                "/.well-known/oauth-authorization-server": "OAuth discovery endpoint",
            },
            "auth": "GitHub OAuth - configure in Claude mobile app with OAuth client ID",
            "oauth_discovery": f"{base_url}/.well-known/oauth-authorization-server",
        }
    )


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
