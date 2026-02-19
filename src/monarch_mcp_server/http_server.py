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
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from hmac import compare_digest

import uvicorn
from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from monarch_mcp_server.oauth_state import (
    OAUTH_JWT_SIGNING_KEY_ENV,
    OAUTH_REDIS_URL_ENV,
    oauth_state_manager,
)
from monarch_mcp_server.tools import register_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_auth_mode() -> str:
    """Get auth mode for remote HTTP server."""
    mode = os.getenv("MCP_AUTH_MODE", "token").strip().lower()
    if mode not in ("token", "oauth", "both"):
        raise ValueError(
            "Invalid MCP_AUTH_MODE. Use 'token' (default), 'oauth', or 'both'."
        )
    return mode


def get_token_auth_secret() -> str:
    """Get required shared token for token auth mode."""
    token = os.getenv("MCP_AUTH_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "MCP_AUTH_TOKEN is required when MCP_AUTH_MODE=token or MCP_AUTH_MODE=both. "
            "Set MCP_AUTH_TOKEN to a long random secret."
        )
    return token


def get_ci_smoke_token() -> str:
    """Get shared token for CI smoke-only MCP endpoint."""
    token = os.getenv("MCP_CI_SMOKE_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "MCP_CI_SMOKE_TOKEN is required when MCP_ENABLE_CI_SMOKE=true."
        )
    return token


def is_ci_smoke_enabled() -> bool:
    return os.getenv("MCP_ENABLE_CI_SMOKE", "false").strip().lower() == "true"


def get_oauth_redis_url() -> str | None:
    """Get optional Redis URL for durable OAuth state."""
    return os.getenv(OAUTH_REDIS_URL_ENV, "").strip() or None


def get_oauth_jwt_signing_key() -> str | None:
    """Get optional JWT signing key for OAuth tokens."""
    return os.getenv(OAUTH_JWT_SIGNING_KEY_ENV, "").strip() or None


def is_oauth_enabled(mode: str) -> bool:
    return mode in ("oauth", "both")


def is_token_enabled(mode: str) -> bool:
    return mode in ("token", "both")


def is_path_for_mount(path: str, mount_prefix: str) -> bool:
    """Return True when request path targets a Starlette mount prefix."""
    normalized = mount_prefix if mount_prefix.startswith("/") else f"/{mount_prefix}"
    normalized = normalized.rstrip("/") or "/"
    if normalized == "/":
        return True
    return path == normalized or path.startswith(f"{normalized}/")


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

    if is_oauth_enabled(auth_mode):
        base_url = get_base_url()
        client_id = os.getenv("GITHUB_CLIENT_ID", "")
        client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")
        redis_url = get_oauth_redis_url()
        signing_key = get_oauth_jwt_signing_key()

        if not client_id or not client_secret:
            raise ValueError(
                "GitHub OAuth credentials required when MCP_AUTH_MODE=oauth or MCP_AUTH_MODE=both. "
                "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET."
            )

        # Redis-backed storage is optional; without it FastMCP uses a local
        # encrypted DiskStore (ephemeral on Cloud Run, but fine for single-user).
        if redis_url is not None and signing_key is not None:
            oauth_storage = oauth_state_manager.configure_storage(
                redis_url, signing_key
            )
            auth_provider = GitHubProvider(
                client_id=client_id,
                client_secret=client_secret,
                base_url=base_url,
                redirect_path="/auth/callback",
                require_authorization_consent=False,
                client_storage=oauth_storage,
                jwt_signing_key=signing_key,
            )
            logger.info("OAuth storage: Redis-backed (durable)")
        else:
            oauth_state_manager.disable_storage()
            auth_provider = GitHubProvider(
                client_id=client_id,
                client_secret=client_secret,
                base_url=base_url,
                redirect_path="/auth/callback",
                require_authorization_consent=False,
            )
            logger.info("OAuth storage: FastMCP default DiskStore (ephemeral)")
    else:
        oauth_state_manager.disable_storage()
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
    """Require Bearer token for selected MCP endpoints in token-capable modes."""

    def __init__(self, app, token: str, protected_mounts: tuple[str, ...]):
        super().__init__(app)
        self.token = token
        self.protected_mounts = protected_mounts

    async def dispatch(self, request: Request, call_next):
        if not any(
            is_path_for_mount(request.url.path, mount)
            for mount in self.protected_mounts
        ):
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


class MCPSmokeTokenAuthMiddleware(BaseHTTPMiddleware):
    """Require dedicated bearer token for /mcp-smoke endpoint."""

    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):
        if not is_path_for_mount(request.url.path, "/mcp-smoke"):
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


class OAuthAutoRepairMiddleware(BaseHTTPMiddleware):
    """Trigger OAuth state repair when invalid_token spikes are detected."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not is_path_for_mount(request.url.path, "/mcp"):
            return response
        if is_path_for_mount(request.url.path, "/mcp-smoke"):
            return response
        if is_path_for_mount(request.url.path, "/mcp-token"):
            return response

        if response.status_code != 401:
            return response

        body = getattr(response, "body", b"")
        if not isinstance(body, (bytes, bytearray)) or b"invalid_token" not in body:
            return response

        should_repair = oauth_state_manager.mark_invalid_token()
        if should_repair:
            repair = await oauth_state_manager.repair()
            if repair.ok:
                logger.warning("oauth_repair_succeeded")
            else:
                logger.error(f"oauth_repair_failed: {repair.message}")
        return response


def create_mcp_smoke_server() -> FastMCP:
    """Create a non-OAuth MCP app used only for CI smoke checks."""
    mcp = FastMCP(
        "Monarch Money MCP Server (CI Smoke)",
        auth=None,
        instructions="Internal MCP endpoint for deployment smoke checks",
    )
    register_tools(mcp)
    return mcp


def create_mcp_token_server() -> FastMCP:
    """Create a token-auth MCP app for mixed auth deployments."""
    mcp = FastMCP(
        "Monarch Money MCP Server (Token Endpoint)",
        auth=None,
        instructions="MCP endpoint secured by shared bearer token",
    )
    register_tools(mcp)
    return mcp


def build_lifespan(*mounted_apps):
    """Compose lifespans for mounted MCP apps so all session managers initialize."""
    apps = [app for app in mounted_apps if app is not None]

    @asynccontextmanager
    async def _lifespan(app):
        if not apps:
            yield
            return
        if len(apps) == 1:
            async with apps[0].lifespan(app):
                yield
            return

        async with apps[0].lifespan(app):
            async with apps[1].lifespan(app):
                if len(apps) == 2:
                    yield
                    return
                async with apps[2].lifespan(app):
                    yield

    return _lifespan


# Health check endpoint (public, no auth required)
async def health_check(request: Request) -> Response:
    """Health check endpoint for monitoring and load balancers."""
    return JSONResponse(
        {
            "status": "healthy",
            "service": "monarch-mcp-server",
            "mode": "liveness_only",
        }
    )


async def readiness_check(request: Request) -> Response:
    """Readiness check that validates auth and MCP wiring."""
    checks: dict[str, bool] = {}
    errors: dict[str, str] = {}
    auth_mode = "unknown"

    try:
        auth_mode = get_auth_mode()
        checks["auth_mode_configured"] = True
    except Exception as e:
        checks["auth_mode_configured"] = False
        errors["auth_mode_configured"] = str(e)

    mcp_server = None
    if checks["auth_mode_configured"]:
        try:
            mcp_server = create_mcp_server()
            checks["mcp_server_initialized"] = True
        except Exception as e:
            checks["mcp_server_initialized"] = False
            errors["mcp_server_initialized"] = str(e)

    if checks.get("mcp_server_initialized") and mcp_server is not None:
        try:
            mcp_server.http_app(path="/mcp")
            checks["mcp_http_app_initialized"] = True
        except Exception as e:
            checks["mcp_http_app_initialized"] = False
            errors["mcp_http_app_initialized"] = str(e)

    if is_token_enabled(auth_mode):
        try:
            get_token_auth_secret()
            checks["token_secret_configured"] = True
        except Exception as e:
            checks["token_secret_configured"] = False
            errors["token_secret_configured"] = str(e)

    if is_oauth_enabled(auth_mode):
        provider_ready = bool(
            mcp_server is not None
            and checks.get("mcp_server_initialized")
            and mcp_server.auth is not None
        )
        checks["oauth_provider_configured"] = provider_ready
        if not provider_ready:
            errors["oauth_provider_configured"] = "OAuth provider is not initialized."
        elif mcp_server is not None and mcp_server.auth is not None:
            try:
                routes = mcp_server.auth.get_well_known_routes(mcp_path="/mcp")
                checks["oauth_discovery_routes_available"] = len(routes) > 0
                if len(routes) == 0:
                    errors["oauth_discovery_routes_available"] = (
                        "No OAuth discovery routes were generated."
                    )
            except Exception as e:
                checks["oauth_discovery_routes_available"] = False
                errors["oauth_discovery_routes_available"] = str(e)
        # Redis-backed storage checks (only when OAuth provider is active and storage is configured)
        if provider_ready and oauth_state_manager.storage is not None:
            store_ok, store_msg = await oauth_state_manager.probe_storage()
            checks["oauth_store_reachable"] = store_ok
            if not store_ok:
                errors["oauth_store_reachable"] = store_msg
            if oauth_state_manager.last_repair is not None:
                checks["oauth_repair_last_status"] = oauth_state_manager.last_repair.ok
                if not oauth_state_manager.last_repair.ok:
                    errors["oauth_repair_last_status"] = (
                        oauth_state_manager.last_repair.message
                    )
            else:
                checks["oauth_repair_last_status"] = True
            checks["oauth_invalid_token_rate_1m"] = (
                oauth_state_manager.invalid_token_rate_1m == 0
            )

    ready = all(checks.values()) if checks else False
    status_code = 200 if ready else 503
    return JSONResponse(
        {
            "status": "ready" if ready else "not_ready",
            "service": "monarch-mcp-server",
            "auth_mode": auth_mode,
            "checks": checks,
            "errors": errors,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        status_code=status_code,
    )


async def root(request: Request) -> Response:
    """Root endpoint with basic info."""
    base_url = get_base_url()
    auth_mode = get_auth_mode()
    auth_description = {
        "token": "Bearer token (single-user mode)",
        "oauth": "GitHub OAuth (advanced mode)",
        "both": "GitHub OAuth on /mcp + shared bearer token on /mcp-token/mcp",
    }[auth_mode]
    mcp_description = {
        "token": "MCP endpoint (requires Authorization: Bearer token)",
        "oauth": "MCP endpoint (requires GitHub OAuth)",
        "both": "MCP endpoint (requires GitHub OAuth; token endpoint at /mcp-token/mcp)",
    }[auth_mode]
    return JSONResponse(
        {
            "service": "Monarch Money MCP Server",
            "description": "MCP server for Monarch Money personal finance",
            "auth_mode": auth_mode,
            "endpoints": {
                "/health": "Health check endpoint (public)",
                "/ready": "Readiness endpoint with auth and MCP checks (public)",
                "/mcp": mcp_description,
                "/mcp-token/mcp": (
                    "Token-auth MCP endpoint (available when MCP_AUTH_MODE=both)"
                ),
                "/mcp-smoke/mcp": "CI smoke MCP endpoint (token auth, when enabled)",
                "/.well-known/oauth-authorization-server": (
                    "OAuth discovery endpoint (oauth/both mode only)"
                ),
            },
            "auth": auth_description,
            "oauth_discovery": (
                f"{base_url}/.well-known/oauth-authorization-server"
                if is_oauth_enabled(auth_mode)
                else None
            ),
        }
    )


def create_app() -> Starlette:
    """Create the Starlette ASGI application."""
    auth_mode = get_auth_mode()
    mcp_server = create_mcp_server()
    token_enabled = is_token_enabled(auth_mode)
    oauth_enabled = is_oauth_enabled(auth_mode)
    token = get_token_auth_secret() if token_enabled else None
    smoke_enabled = is_ci_smoke_enabled()
    smoke_token = get_ci_smoke_token() if smoke_enabled else None

    # Get the HTTP app from FastMCP (includes OAuth routes)
    mcp_app = mcp_server.http_app(path="/mcp")
    token_app = None
    if auth_mode == "both":
        token_server = create_mcp_token_server()
        token_app = token_server.http_app(path="/mcp")

    smoke_app = None
    if smoke_enabled:
        smoke_server = create_mcp_smoke_server()
        smoke_app = smoke_server.http_app(path="/mcp")

    # Get well-known routes for OAuth discovery
    if oauth_enabled and mcp_server.auth:
        well_known_routes = mcp_server.auth.get_well_known_routes(mcp_path="/mcp")
    else:
        well_known_routes = []

    # Create main app combining everything
    app = Starlette(
        debug=os.getenv("DEBUG", "false").lower() == "true",
        routes=[
            Route("/", root),
            Route("/health", health_check),
            Route("/ready", readiness_check),
            # Well-known routes at root for OAuth discovery
            *well_known_routes,
            *([Mount("/mcp-token", app=token_app)] if token_app is not None else []),
            # Mount CI smoke app before main MCP app so route resolution is deterministic.
            *([Mount("/mcp-smoke", app=smoke_app)] if smoke_app is not None else []),
            # Mount the MCP app
            Mount("/", app=mcp_app),
        ],
        lifespan=build_lifespan(mcp_app, token_app, smoke_app),
    )

    if token is not None:
        protected_mounts = ("/mcp",) if auth_mode == "token" else ("/mcp-token",)
        app.add_middleware(  # type: ignore[arg-type]
            MCPTokenAuthMiddleware,
            token=token,
            protected_mounts=protected_mounts,
        )
        if auth_mode == "token":
            logger.info("Monarch Money MCP HTTP Server initialized in token auth mode")
        else:
            logger.info(
                "Monarch Money MCP HTTP Server initialized with mixed auth "
                "(OAuth on /mcp, token on /mcp-token/mcp)"
            )

    if oauth_enabled:
        # Only add auto-repair middleware when Redis-backed storage is active
        if oauth_state_manager.storage is not None:
            app.add_middleware(OAuthAutoRepairMiddleware)  # type: ignore[arg-type]
        if auth_mode == "oauth":
            logger.info("Monarch Money MCP HTTP Server initialized in GitHub OAuth mode")

    if smoke_enabled and smoke_token is not None:
        app.add_middleware(MCPSmokeTokenAuthMiddleware, token=smoke_token)  # type: ignore[arg-type]
        logger.info("CI smoke MCP endpoint enabled at /mcp-smoke")

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
    if auth_mode == "both":
        logger.info(f"Token MCP endpoint: {base_url}/mcp-token/mcp")
    logger.info(f"Readiness check: {base_url}/ready")
    if is_oauth_enabled(auth_mode):
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
