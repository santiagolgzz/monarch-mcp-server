"""Tests for HTTP server module."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure module can be imported by setting credentials before first import
# This works around the module-level create_app() call
os.environ.setdefault("GITHUB_CLIENT_ID", "test_client_id_for_import")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test_client_secret_for_import")


class TestGetBaseUrl:
    """Tests for the get_base_url function."""

    def test_explicit_override(self):
        """Verify BASE_URL environment variable takes precedence."""
        from monarch_mcp_server.http_server import get_base_url

        with patch.dict(os.environ, {"BASE_URL": "https://custom.example.com/"}):
            result = get_base_url()
            # Should strip trailing slash
            assert result == "https://custom.example.com"

    def test_railway_domain(self):
        """Verify Railway domain detection."""
        from monarch_mcp_server.http_server import get_base_url

        # Remove BASE_URL but keep GitHub credentials for module-level app creation
        env_for_test = {k: v for k, v in os.environ.items() if k != "BASE_URL"}
        env_for_test["RAILWAY_PUBLIC_DOMAIN"] = "my-app.railway.app"
        env_for_test["PORT"] = "8000"

        with patch.dict(os.environ, env_for_test, clear=True):
            result = get_base_url()
            assert result == "https://my-app.railway.app"

    def test_localhost_fallback(self):
        """Verify localhost fallback when no special env vars set."""
        from monarch_mcp_server.http_server import get_base_url

        # Keep GitHub credentials but remove BASE_URL and RAILWAY_PUBLIC_DOMAIN
        env_for_test = {
            k: v
            for k, v in os.environ.items()
            if k not in ("BASE_URL", "RAILWAY_PUBLIC_DOMAIN")
        }
        env_for_test["HOST"] = "localhost"
        env_for_test["PORT"] = "8000"

        with patch.dict(os.environ, env_for_test, clear=True):
            result = get_base_url()
            assert result == "http://localhost:8000"

    def test_custom_host_and_port(self):
        """Verify custom HOST and PORT environment variables."""
        from monarch_mcp_server.http_server import get_base_url

        # Keep GitHub credentials but test custom HOST/PORT
        env_for_test = {
            k: v
            for k, v in os.environ.items()
            if k not in ("BASE_URL", "RAILWAY_PUBLIC_DOMAIN")
        }
        env_for_test["HOST"] = "0.0.0.0"
        env_for_test["PORT"] = "9000"

        with patch.dict(os.environ, env_for_test, clear=True):
            result = get_base_url()
            assert result == "http://0.0.0.0:9000"


class TestCreateMCPServer:
    """Tests for the create_mcp_server function."""

    def test_missing_credentials_raises_error(self):
        """Verify create_mcp_server raises when GitHub credentials are missing."""
        # create_mcp_server now validates credentials and raises ValueError

        import monarch_mcp_server.http_server as http_server_module

        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "",
                "GITHUB_CLIENT_SECRET": "",
                "BASE_URL": "http://localhost:8000",
            },
        ):
            with pytest.raises(ValueError, match="GitHub OAuth credentials required"):
                # Call the function directly - it validates credentials early
                http_server_module.create_mcp_server()

    def test_with_credentials(self):
        """Verify server is created with GitHub credentials."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "test_client_id",
                "GITHUB_CLIENT_SECRET": "test_client_secret",
                "BASE_URL": "http://localhost:8000",
            },
        ):
            from monarch_mcp_server.http_server import create_mcp_server

            server = create_mcp_server()

            # Server should have auth configured
            assert server.auth is not None


class TestHealthCheck:
    """Tests for the health_check endpoint."""

    @pytest.mark.asyncio
    async def test_returns_minimal_info(self):
        """Verify health check returns only status and service (no credential info)."""
        import json

        from starlette.requests import Request

        from monarch_mcp_server.http_server import health_check

        mock_request = MagicMock(spec=Request)
        response = await health_check(mock_request)

        assert response.status_code == 200
        data = json.loads(response.body.decode())
        # Should only contain status and service - no credential info
        assert data == {"status": "healthy", "service": "monarch-mcp-server"}

    @pytest.mark.asyncio
    async def test_without_credentials(self):
        """Verify health check when no Monarch credentials exist."""
        # Save and clear monarch-specific env vars
        saved_env = {}
        for key in ["MONARCH_TOKEN", "MONARCH_EMAIL", "MONARCH_PASSWORD"]:
            saved_env[key] = os.environ.pop(key, None)

        try:
            with patch(
                "monarch_mcp_server.secure_session.SecureMonarchSession.load_token",
                return_value=None,
            ):
                from starlette.requests import Request

                from monarch_mcp_server.http_server import health_check

                mock_request = MagicMock(spec=Request)
                response = await health_check(mock_request)

                assert response.status_code == 200
                data = response.body.decode()
                assert "healthy" in data
        finally:
            # Restore env vars
            for key, value in saved_env.items():
                if value is not None:
                    os.environ[key] = value

    @pytest.mark.asyncio
    async def test_response_structure(self):
        """Verify health check response contains only minimal fields."""
        import json

        from starlette.requests import Request

        from monarch_mcp_server.http_server import health_check

        mock_request = MagicMock(spec=Request)
        response = await health_check(mock_request)

        data = json.loads(response.body.decode())

        # Health endpoint should only expose status and service
        # NOT credential status (security: no information disclosure)
        assert "status" in data
        assert "service" in data
        assert "has_monarch_credentials" not in data
        assert "github_oauth_configured" not in data
        assert "base_url" not in data


class TestRootEndpoint:
    """Tests for the root endpoint."""

    @pytest.mark.asyncio
    async def test_response_structure(self):
        """Verify root endpoint returns expected info."""
        with patch.dict(
            os.environ,
            {
                "BASE_URL": "http://localhost:8000",
                "GITHUB_CLIENT_ID": "test_id",
                "GITHUB_CLIENT_SECRET": "test_secret",
            },
        ):
            import json

            from starlette.requests import Request

            from monarch_mcp_server.http_server import root

            mock_request = MagicMock(spec=Request)
            response = await root(mock_request)

            data = json.loads(response.body.decode())

            assert "service" in data
            assert "Monarch" in data["service"]
            assert "endpoints" in data
            assert "/health" in data["endpoints"]
            assert "/mcp" in data["endpoints"]


class TestCreateApp:
    """Tests for the create_app function."""

    def test_creates_starlette_app(self):
        """Verify create_app returns a Starlette application."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "test_id",
                "GITHUB_CLIENT_SECRET": "test_secret",
                "BASE_URL": "http://localhost:8000",
            },
        ):
            from starlette.applications import Starlette

            from monarch_mcp_server.http_server import create_app

            app = create_app()

            # App should be a Starlette instance
            assert isinstance(app, Starlette)


class TestMain:
    """Tests for the main entry point."""

    def test_exits_without_oauth_credentials(self):
        """Verify main exits when GitHub OAuth credentials are missing."""
        with patch.dict(
            os.environ,
            {"GITHUB_CLIENT_ID": "", "GITHUB_CLIENT_SECRET": ""},
        ):
            with patch("monarch_mcp_server.http_server.logger"):
                from monarch_mcp_server.http_server import main

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

    def test_logs_startup_info(self):
        """Verify main logs startup information."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "test_id",
                "GITHUB_CLIENT_SECRET": "test_secret",
                "BASE_URL": "http://localhost:8000",
            },
        ):
            with patch("monarch_mcp_server.http_server.uvicorn.run"):
                with patch("monarch_mcp_server.http_server.logger") as mock_logger:
                    from monarch_mcp_server.http_server import main

                    main()

                    # Should log startup info
                    assert mock_logger.info.call_count >= 2

    def test_calls_uvicorn_run(self):
        """Verify main calls uvicorn.run with correct parameters."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "test_id",
                "GITHUB_CLIENT_SECRET": "test_secret",
                "HOST": "127.0.0.1",
                "PORT": "9000",
            },
        ):
            with patch("monarch_mcp_server.http_server.uvicorn.run") as mock_uvicorn:
                with patch("monarch_mcp_server.http_server.logger"):
                    from monarch_mcp_server.http_server import main

                    main()

                    mock_uvicorn.assert_called_once()
                    call_kwargs = mock_uvicorn.call_args.kwargs
                    assert call_kwargs["host"] == "127.0.0.1"
                    assert call_kwargs["port"] == 9000


class TestIntegration:
    """Integration-style endpoint tests without ASGI client lifespan startup."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health endpoint behavior."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "test_id",
                "GITHUB_CLIENT_SECRET": "test_secret",
                "BASE_URL": "http://localhost:8000",
            },
        ):
            from starlette.requests import Request

            from monarch_mcp_server.http_server import health_check

            response = await health_check(MagicMock(spec=Request))
            assert response.status_code == 200
            assert "healthy" in response.body.decode()

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """Test root endpoint behavior."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "test_id",
                "GITHUB_CLIENT_SECRET": "test_secret",
                "BASE_URL": "http://localhost:8000",
            },
        ):
            from starlette.requests import Request

            from monarch_mcp_server.http_server import root

            response = await root(MagicMock(spec=Request))
            assert response.status_code == 200
            assert "Monarch Money MCP Server" in response.body.decode()
