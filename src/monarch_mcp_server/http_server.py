"""
HTTP/SSE server wrapper for Monarch Money MCP Server.

This module enables hosting the MCP server online for use with Claude mobile app
and other remote MCP clients. It wraps the FastMCP server with:
- SSE (Server-Sent Events) transport for MCP protocol
- API key authentication for security
- Health check endpoint for monitoring

Usage:
    # Set required environment variables:
    export MCP_API_KEY="your-secure-api-key"
    export MONARCH_TOKEN="your-monarch-token"  # From login_setup.py

    # Run the server:
    python -m monarch_mcp_server.http_server

    # Or with uvicorn directly:
    uvicorn monarch_mcp_server.http_server:app --host 0.0.0.0 --port 8000
"""

import os
import logging
import secrets
from typing import Optional

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, Mount

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_api_key() -> Optional[str]:
    """Get the API key from environment variable."""
    return os.getenv("MCP_API_KEY")


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate API key for all MCP requests."""

    # Paths that don't require authentication
    PUBLIC_PATHS = {"/health", "/"}

    async def dispatch(self, request: Request, call_next):
        # Allow public paths without auth
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Get expected API key
        expected_key = get_api_key()

        if not expected_key:
            logger.error("MCP_API_KEY environment variable not set!")
            return JSONResponse(
                {"error": "Server misconfigured - API key not set"},
                status_code=500
            )

        # Check Authorization header (Bearer token)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:]  # Remove "Bearer " prefix
        else:
            # Also check X-API-Key header as fallback
            provided_key = request.headers.get("X-API-Key", "")

        # Validate API key using constant-time comparison
        if not provided_key or not secrets.compare_digest(provided_key, expected_key):
            logger.warning(f"Unauthorized request from {request.client.host if request.client else 'unknown'}")
            return JSONResponse(
                {"error": "Unauthorized - Invalid or missing API key"},
                status_code=401
            )

        return await call_next(request)


async def health_check(request: Request) -> Response:
    """Health check endpoint for monitoring and load balancers."""
    from monarch_mcp_server.secure_session import secure_session

    # Check if we have valid Monarch credentials
    has_credentials = bool(os.getenv("MONARCH_TOKEN")) or secure_session.load_token() is not None

    status = {
        "status": "healthy",
        "service": "monarch-mcp-server",
        "has_monarch_credentials": has_credentials,
        "api_key_configured": bool(get_api_key()),
    }

    return JSONResponse(status)


async def root(request: Request) -> Response:
    """Root endpoint with basic info."""
    return JSONResponse({
        "service": "Monarch Money MCP Server",
        "description": "MCP server for Monarch Money personal finance",
        "endpoints": {
            "/health": "Health check endpoint",
            "/sse": "SSE endpoint for MCP protocol (requires API key)",
            "/messages/": "Message endpoint for MCP protocol (requires API key)",
        },
        "auth": "Use Authorization: Bearer <your-api-key> header"
    })


def create_app() -> Starlette:
    """Create the Starlette ASGI application with MCP SSE support."""
    from monarch_mcp_server.server import mcp

    # Get the SSE app from FastMCP
    sse_app = mcp.sse_app()

    # Create main app with middleware
    app = Starlette(
        debug=os.getenv("DEBUG", "false").lower() == "true",
        routes=[
            Route("/", root),
            Route("/health", health_check),
            # Mount the MCP SSE app
            Mount("/", app=sse_app),
        ],
        middleware=[
            Middleware(APIKeyAuthMiddleware),
        ],
    )

    logger.info("Monarch Money MCP HTTP Server initialized")

    return app


# Create the ASGI app instance
app = create_app()


def main():
    """Run the HTTP server using uvicorn."""
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    # Validate configuration
    if not get_api_key():
        logger.error("=" * 60)
        logger.error("ERROR: MCP_API_KEY environment variable is required!")
        logger.error("Generate a secure key: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        logger.error("Then set: export MCP_API_KEY='your-generated-key'")
        logger.error("=" * 60)
        raise SystemExit(1)

    if not os.getenv("MONARCH_TOKEN"):
        logger.warning("=" * 60)
        logger.warning("WARNING: MONARCH_TOKEN not set")
        logger.warning("Run 'python login_setup.py' locally, then copy the token")
        logger.warning("Or set MONARCH_EMAIL and MONARCH_PASSWORD for auto-login")
        logger.warning("=" * 60)

    logger.info(f"Starting Monarch Money MCP Server on http://{host}:{port}")
    logger.info("SSE endpoint: /sse")
    logger.info("Health check: /health")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
