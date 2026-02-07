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
from hmac import compare_digest

import uvicorn
from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from monarch_mcp_server.tools import register_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_auth_mode() -> str:
    """Get auth mode for remote HTTP server."""
    mode = os.getenv("MCP_AUTH_MODE", "token").strip().lower()
    if mode not in ("token", "oauth"):
        raise ValueError("Invalid MCP_AUTH_MODE. Use 'token' (default) or 'oauth'.")
    return mode


def get_token_auth_secret() -> str:
    """Get required shared token for token auth mode."""
    token = os.getenv("MCP_AUTH_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "MCP_AUTH_TOKEN is required when MCP_AUTH_MODE=token. "
            "Set MCP_AUTH_TOKEN to a long random secret."
        )
    return token


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
    """Create the FastMCP server with selected auth mode and all Monarch tools.

    Raises:
        ValueError: If auth configuration is invalid.
    """
    auth_mode = get_auth_mode()
    auth_provider = None

    if auth_mode == "oauth":
        base_url = get_base_url()
        client_id = os.getenv("GITHUB_CLIENT_ID", "")
        client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")

        if not client_id or not client_secret:
            raise ValueError(
                "GitHub OAuth credentials required when MCP_AUTH_MODE=oauth. "
                "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET."
            )

        auth_provider = GitHubProvider(
            client_id=client_id,
            client_secret=client_secret,
            base_url=base_url,
            redirect_path="/auth/callback",
            require_authorization_consent=False,
        )
    else:
        # Validate token mode config up front so failures are clear at startup.
        get_token_auth_secret()

    mcp = FastMCP(
        "Monarch Money MCP Server",
        auth=auth_provider,
        instructions="MCP server for Monarch Money personal finance management",
    )

    # Register all shared tools
    register_tools(mcp)

    return mcp


class MCPTokenAuthMiddleware(BaseHTTPMiddleware):
    """Require Bearer token for MCP endpoint in single-user token mode."""

    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "unauthorized", "message": "Bearer token required"},
                status_code=401,
            )

        candidate = auth_header.removeprefix("Bearer ").strip()
        if not candidate or not compare_digest(candidate, self.token):
            return JSONResponse(
                {"error": "unauthorized", "message": "Invalid bearer token"},
                status_code=401,
            )

        return await call_next(request)


# Health check endpoint (public, no auth required)
async def health_check(request: Request) -> Response:
    """Health check endpoint for monitoring and load balancers."""
    return JSONResponse(
        {
            "status": "healthy",
            "service": "monarch-mcp-server",
        }
    )


async def root(request: Request) -> Response:
    """Root endpoint with basic info."""
    base_url = get_base_url()
    auth_mode = get_auth_mode()
    auth_description = (
        "Bearer token (single-user mode)"
        if auth_mode == "token"
        else "GitHub OAuth (advanced mode)"
    )
    return JSONResponse(
        {
            "service": "Monarch Money MCP Server",
            "description": "MCP server for Monarch Money personal finance",
            "auth_mode": auth_mode,
            "endpoints": {
                "/health": "Health check endpoint (public)",
                "/mcp": (
                    "MCP endpoint (requires Authorization: Bearer token)"
                    if auth_mode == "token"
                    else "MCP endpoint (requires GitHub OAuth)"
                ),
                "/.well-known/oauth-authorization-server": (
                    "OAuth discovery endpoint (oauth mode only)"
                ),
            },
            "auth": auth_description,
            "oauth_discovery": (
                f"{base_url}/.well-known/oauth-authorization-server"
                if auth_mode == "oauth"
                else None
            ),
        }
    )


def create_app() -> Starlette:
    """Create the Starlette ASGI application."""
    auth_mode = get_auth_mode()
    mcp_server = create_mcp_server()
    token = get_token_auth_secret() if auth_mode == "token" else None

    # Get the HTTP app from FastMCP (includes OAuth routes)
    mcp_app = mcp_server.http_app(path="/mcp")

    # Get well-known routes for OAuth discovery
    if auth_mode == "oauth" and mcp_server.auth:
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

    if auth_mode == "token" and token is not None:
        app.add_middleware(MCPTokenAuthMiddleware, token=token)  # type: ignore[arg-type]
        logger.info("Monarch Money MCP HTTP Server initialized in token auth mode")
    else:
        logger.info("Monarch Money MCP HTTP Server initialized in GitHub OAuth mode")

    return app


# Lazy app creation for ASGI servers (gunicorn, etc.)
# This allows importing the module without requiring OAuth credentials
_app: Starlette | None = None


def get_app() -> Starlette:
    """Get or create the ASGI application.

    Raises:
        ValueError: If OAuth credentials are not configured.
    """
    global _app
    if _app is None:
        _app = create_app()
    return _app


def main():
    """Run the HTTP server using uvicorn."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    auth_mode = get_auth_mode()

    # Validate by attempting to create the app (will raise if misconfigured)
    try:
        application = get_app()
    except ValueError as e:
        logger.error("=" * 60)
        logger.error(f"ERROR: {e}")
        logger.error("=" * 60)
        raise SystemExit(1)

    base_url = get_base_url()
    logger.info(f"Starting Monarch Money MCP Server on {base_url}")
    logger.info(f"Auth mode: {auth_mode}")
    logger.info(f"MCP endpoint: {base_url}/mcp")
    if auth_mode == "oauth":
        logger.info(
            f"OAuth discovery: {base_url}/.well-known/oauth-authorization-server"
        )
    logger.info(f"Health check: {base_url}/health")

    uvicorn.run(
        application,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
