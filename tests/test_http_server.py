"""Tests for HTTP server module."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient


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
        "BASE_URL": "http://localhost:8000",
    }
    env.update(overrides)
    return env


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


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_returns_minimal_info(self):
        from starlette.requests import Request

        from monarch_mcp_server.http_server import health_check

        response = await health_check(MagicMock(spec=Request))
        assert response.status_code == 200
        assert json.loads(response.body.decode()) == {
            "status": "healthy",
            "service": "monarch-mcp-server",
        }


class TestRootEndpoint:
    @pytest.mark.asyncio
    async def test_reports_token_mode(self):
        from starlette.requests import Request

        from monarch_mcp_server.http_server import root

        with patch.dict(os.environ, _token_env(), clear=True):
            response = await root(MagicMock(spec=Request))
            data = json.loads(response.body.decode())
            assert data["auth_mode"] == "token"
            assert "Bearer" in data["endpoints"]["/mcp"]
            assert data["oauth_discovery"] is None

    @pytest.mark.asyncio
    async def test_reports_oauth_mode(self):
        from starlette.requests import Request

        from monarch_mcp_server.http_server import root

        with patch.dict(os.environ, _oauth_env(), clear=True):
            response = await root(MagicMock(spec=Request))
            data = json.loads(response.body.decode())
            assert data["auth_mode"] == "oauth"
            assert data["oauth_discovery"].endswith(
                "/.well-known/oauth-authorization-server"
            )


class TestCreateApp:
    def test_token_mode_adds_bearer_protection_to_mcp(self):
        from monarch_mcp_server.http_server import create_app

        with patch.dict(os.environ, _token_env(), clear=True):
            app = create_app()

        client = TestClient(app)

        unauthorized = client.get("/mcp")
        assert unauthorized.status_code == 401

    def test_oauth_mode_keeps_well_known_discovery_route(self):
        from monarch_mcp_server.http_server import create_app

        with patch.dict(os.environ, _oauth_env(), clear=True):
            app = create_app()

        client = TestClient(app)
        response = client.get("/.well-known/oauth-authorization-server")
        assert response.status_code == 200


class TestTokenMiddleware:
    def test_valid_bearer_passes_through(self):
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        from monarch_mcp_server.http_server import MCPTokenAuthMiddleware

        async def ok(_request):
            return JSONResponse({"ok": True})

        app = Starlette(routes=[Route("/mcp", ok)])
        app.add_middleware(MCPTokenAuthMiddleware, token="test-token")

        client = TestClient(app)
        response = client.get("/mcp", headers={"Authorization": "Bearer test-token"})
        assert response.status_code == 200


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
