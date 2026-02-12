"""Tests for HTTP server module."""

import json
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


def _token_env(**overrides):
    env = {
        "MCP_AUTH_MODE": "token",
        "MCP_AUTH_TOKEN": "test-token",
        "BASE_URL": "http://localhost:8000",
    }
    env.update(overrides)
    return env


def _oauth_env(**overrides):
    env = {
        "MCP_AUTH_MODE": "oauth",
        "GITHUB_CLIENT_ID": "test_client_id",
        "GITHUB_CLIENT_SECRET": "test_client_secret",
        "MCP_OAUTH_REDIS_URL": "redis://localhost:6379/0",
        "MCP_OAUTH_JWT_SIGNING_KEY": "test-jwt-signing-key",
        "BASE_URL": "http://localhost:8000",
    }
    env.update(overrides)
    return env


def _build_fake_mcp_server(include_oauth_routes: bool = False):
    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    async def _mcp_ok(_request):
        return JSONResponse({"ok": True})

    async def _oauth_discovery(_request):
        return JSONResponse({"issuer": "http://localhost:8000"})

    def _http_app(path="/mcp"):
        app = Starlette(
            routes=[Route(path, _mcp_ok)],
            lifespan=_noop_lifespan,
        )
        # Mirror the attribute shape used by create_app() with real FastMCP apps.
        app.lifespan = _noop_lifespan  # type: ignore[attr-defined]
        return app

    auth = None
    if include_oauth_routes:
        auth = SimpleNamespace(
            get_well_known_routes=lambda mcp_path="/mcp": [
                Route("/.well-known/oauth-authorization-server", _oauth_discovery)
            ]
        )

    return SimpleNamespace(auth=auth, http_app=_http_app)


class TestAuthModeHelpers:
    def test_get_auth_mode_default(self):
        from monarch_mcp_server.http_server import get_auth_mode

        with patch.dict(os.environ, {}, clear=True):
            assert get_auth_mode() == "token"

    def test_get_auth_mode_rejects_invalid_value(self):
        from monarch_mcp_server.http_server import get_auth_mode

        with patch.dict(os.environ, {"MCP_AUTH_MODE": "banana"}, clear=True):
            with pytest.raises(ValueError, match="Invalid MCP_AUTH_MODE"):
                get_auth_mode()

    def test_get_token_auth_secret_requires_value(self):
        from monarch_mcp_server.http_server import get_token_auth_secret

        with patch.dict(os.environ, {"MCP_AUTH_TOKEN": ""}, clear=True):
            with pytest.raises(ValueError, match="MCP_AUTH_TOKEN is required"):
                get_token_auth_secret()


class TestGetBaseUrl:
    def test_explicit_override(self):
        from monarch_mcp_server.http_server import get_base_url

        with patch.dict(os.environ, {"BASE_URL": "https://custom.example.com/"}):
            assert get_base_url() == "https://custom.example.com"

    def test_railway_domain(self):
        from monarch_mcp_server.http_server import get_base_url

        with patch.dict(
            os.environ,
            {"RAILWAY_PUBLIC_DOMAIN": "my-app.railway.app", "PORT": "8000"},
            clear=True,
        ):
            assert get_base_url() == "https://my-app.railway.app"


class TestCreateMCPServer:
    def test_token_mode_creates_server_without_github_oauth(self):
        from monarch_mcp_server.http_server import create_mcp_server

        with patch.dict(os.environ, _token_env(), clear=True):
            server = create_mcp_server()
            assert server.auth is None

    def test_oauth_mode_missing_credentials_raises_error(self):
        import monarch_mcp_server.http_server as http_server_module

        with patch.dict(
            os.environ,
            _oauth_env(GITHUB_CLIENT_ID="", GITHUB_CLIENT_SECRET=""),
            clear=True,
        ):
            with pytest.raises(
                ValueError,
                match="GitHub OAuth credentials required when MCP_AUTH_MODE=oauth",
            ):
                http_server_module.create_mcp_server()

    def test_oauth_mode_with_credentials_sets_auth(self):
        from monarch_mcp_server.http_server import create_mcp_server

        with patch.dict(os.environ, _oauth_env(), clear=True):
            server = create_mcp_server()
            assert server.auth is not None

    def test_oauth_mode_without_redis_uses_default_storage(self):
        """OAuth works without Redis — falls back to FastMCP DiskStore."""
        from monarch_mcp_server.http_server import create_mcp_server

        with patch.dict(os.environ, _oauth_env(MCP_OAUTH_REDIS_URL=""), clear=True):
            server = create_mcp_server()
            assert server.auth is not None

    def test_oauth_mode_without_jwt_key_uses_default(self):
        """OAuth works without explicit JWT key — FastMCP derives from client_secret."""
        from monarch_mcp_server.http_server import create_mcp_server

        with patch.dict(
            os.environ,
            _oauth_env(MCP_OAUTH_JWT_SIGNING_KEY=""),
            clear=True,
        ):
            server = create_mcp_server()
            assert server.auth is not None


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_returns_minimal_info(self):
        from starlette.requests import Request

        from monarch_mcp_server.http_server import health_check

        response = await health_check(MagicMock(spec=Request))
        assert response.status_code == 200
        body = response.body.decode()  # type: ignore[union-attr]
        assert json.loads(body) == {
            "status": "healthy",
            "service": "monarch-mcp-server",
            "mode": "liveness_only",
        }


class TestReadinessCheck:
    @pytest.mark.asyncio
    async def test_token_mode_ready(self):
        from starlette.requests import Request

        from monarch_mcp_server.http_server import readiness_check

        with patch.dict(os.environ, _token_env(), clear=True):
            with patch(
                "monarch_mcp_server.http_server.create_mcp_server",
                return_value=_build_fake_mcp_server(),
            ):
                response = await readiness_check(MagicMock(spec=Request))

        body = response.body.decode()  # type: ignore[union-attr]
        payload = json.loads(body)
        assert response.status_code == 200
        assert payload["status"] == "ready"
        assert payload["auth_mode"] == "token"
        assert payload["checks"]["auth_mode_configured"] is True
        assert payload["checks"]["mcp_server_initialized"] is True
        assert payload["checks"]["mcp_http_app_initialized"] is True

    @pytest.mark.asyncio
    async def test_oauth_mode_not_ready_when_credentials_missing(self):
        from starlette.requests import Request

        from monarch_mcp_server.http_server import readiness_check

        with patch.dict(
            os.environ,
            _oauth_env(GITHUB_CLIENT_ID="", GITHUB_CLIENT_SECRET=""),
            clear=True,
        ):
            response = await readiness_check(MagicMock(spec=Request))

        body = response.body.decode()  # type: ignore[union-attr]
        payload = json.loads(body)
        assert response.status_code == 503
        assert payload["status"] == "not_ready"
        assert payload["auth_mode"] == "oauth"
        assert payload["checks"]["mcp_server_initialized"] is False
        assert "mcp_server_initialized" in payload["errors"]


class TestRootEndpoint:
    @pytest.mark.asyncio
    async def test_reports_token_mode(self):
        from starlette.requests import Request

        from monarch_mcp_server.http_server import root

        with patch.dict(os.environ, _token_env(), clear=True):
            response = await root(MagicMock(spec=Request))
            body = response.body.decode()  # type: ignore[union-attr]
            data = json.loads(body)
            assert data["auth_mode"] == "token"
            assert "/ready" in data["endpoints"]
            assert "Bearer" in data["endpoints"]["/mcp"]
            assert data["oauth_discovery"] is None

    @pytest.mark.asyncio
    async def test_reports_oauth_mode(self):
        from starlette.requests import Request

        from monarch_mcp_server.http_server import root

        with patch.dict(os.environ, _oauth_env(), clear=True):
            response = await root(MagicMock(spec=Request))
            body = response.body.decode()  # type: ignore[union-attr]
            data = json.loads(body)
            assert data["auth_mode"] == "oauth"
            assert data["oauth_discovery"].endswith(
                "/.well-known/oauth-authorization-server"
            )


class TestCreateApp:
    def test_token_mode_adds_bearer_protection_to_mcp(self):
        from monarch_mcp_server.http_server import MCPTokenAuthMiddleware, create_app

        with patch.dict(os.environ, _token_env(), clear=True):
            with patch(
                "monarch_mcp_server.http_server.create_mcp_server",
                return_value=_build_fake_mcp_server(),
            ):
                app = create_app()

        middleware_classes = [m.cls for m in app.user_middleware]
        assert MCPTokenAuthMiddleware in middleware_classes

    def test_oauth_mode_keeps_well_known_discovery_route(self):
        from monarch_mcp_server.http_server import OAuthAutoRepairMiddleware, create_app

        with patch.dict(os.environ, _oauth_env(), clear=True):
            with patch(
                "monarch_mcp_server.http_server.create_mcp_server",
                return_value=_build_fake_mcp_server(include_oauth_routes=True),
            ):
                with patch(
                    "monarch_mcp_server.http_server.oauth_state_manager"
                ) as mock_mgr:
                    mock_mgr.storage = "fake-redis"  # simulate Redis configured
                    app = create_app()

        route_paths = [getattr(route, "path", None) for route in app.routes]
        middleware_classes = [m.cls for m in app.user_middleware]
        assert OAuthAutoRepairMiddleware in middleware_classes
        assert "/.well-known/oauth-authorization-server" in route_paths

    def test_smoke_mode_adds_smoke_endpoint_and_middleware(self):
        from monarch_mcp_server.http_server import (
            MCPSmokeTokenAuthMiddleware,
            create_app,
        )

        with patch.dict(
            os.environ,
            _token_env(MCP_ENABLE_CI_SMOKE="true", MCP_CI_SMOKE_TOKEN="smoke-token"),
            clear=True,
        ):
            with patch(
                "monarch_mcp_server.http_server.create_mcp_server",
                return_value=_build_fake_mcp_server(),
            ):
                with patch(
                    "monarch_mcp_server.http_server.create_mcp_smoke_server",
                    return_value=_build_fake_mcp_server(),
                ):
                    app = create_app()

        route_paths = [getattr(route, "path", None) for route in app.routes]
        middleware_classes = [m.cls for m in app.user_middleware]
        assert "/mcp-smoke" in route_paths
        assert MCPSmokeTokenAuthMiddleware in middleware_classes


class TestTokenMiddleware:
    @pytest.mark.asyncio
    async def test_valid_bearer_passes_through(self):
        from starlette.requests import Request
        from starlette.responses import JSONResponse

        from monarch_mcp_server.http_server import MCPTokenAuthMiddleware

        middleware = MCPTokenAuthMiddleware(app=MagicMock(), token="test-token")
        request = MagicMock(spec=Request)
        request.url.path = "/mcp"
        request.headers = {"Authorization": "Bearer test-token"}

        async def call_next(_request):
            return JSONResponse({"ok": True})

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200


class TestSmokeTokenMiddleware:
    @pytest.mark.asyncio
    async def test_missing_bearer_is_rejected(self):
        from starlette.requests import Request

        from monarch_mcp_server.http_server import MCPSmokeTokenAuthMiddleware

        middleware = MCPSmokeTokenAuthMiddleware(app=MagicMock(), token="smoke-token")
        request = MagicMock(spec=Request)
        request.url.path = "/mcp-smoke"
        request.headers = {}

        async def call_next(_request):
            return JSONResponse({"ok": True})

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 401


class TestMain:
    def test_exits_when_token_mode_missing_token(self):
        with patch.dict(
            os.environ,
            {"MCP_AUTH_MODE": "token", "MCP_AUTH_TOKEN": ""},
            clear=True,
        ):
            with patch("monarch_mcp_server.http_server.logger"):
                from monarch_mcp_server.http_server import main

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

    def test_calls_uvicorn_run(self):
        with patch.dict(
            os.environ,
            _token_env(HOST="127.0.0.1", PORT="9000"),
            clear=True,
        ):
            with patch("monarch_mcp_server.http_server.uvicorn.run") as mock_uvicorn:
                with patch("monarch_mcp_server.http_server.logger"):
                    from monarch_mcp_server.http_server import main

                    main()

                    mock_uvicorn.assert_called_once()
                    kwargs = mock_uvicorn.call_args.kwargs
                    assert kwargs["host"] == "127.0.0.1"
                    assert kwargs["port"] == 9000
