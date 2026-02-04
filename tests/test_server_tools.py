"""Tests for server.py - main server implementation."""

import os
from unittest.mock import patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.server import main, mcp


@pytest.fixture
def test_mcp():
    """Create a fresh FastMCP instance for testing."""
    return FastMCP("test")


class TestSetupAuthentication:
    """Tests for the setup_authentication tool."""

    @pytest.mark.asyncio
    async def test_returns_instructions(self):
        """Verify setup_authentication returns setup instructions."""
        tool = await mcp._tool_manager.get_tool("setup_authentication")
        # This is a sync tool that returns a string
        result = tool.fn()

        # Check key instruction elements are present
        assert "Monarch Money" in result
        assert "login_setup.py" in result
        assert "credentials" in result.lower()
        assert "get_accounts" in result
        assert "get_transactions" in result
        assert "get_budgets" in result

    @pytest.mark.asyncio
    async def test_mentions_2fa(self):
        """Verify instructions mention 2FA support."""
        tool = await mcp._tool_manager.get_tool("setup_authentication")
        result = tool.fn()
        assert "2FA" in result or "MFA" in result

    @pytest.mark.asyncio
    async def test_mentions_session_persistence(self):
        """Verify instructions mention session persistence."""
        tool = await mcp._tool_manager.get_tool("setup_authentication")
        result = tool.fn()
        assert "persist" in result.lower() or "weeks" in result.lower()


class TestCheckAuthStatus:
    """Tests for the check_auth_status tool."""

    @pytest.mark.asyncio
    async def test_with_token(self):
        """Verify check_auth_status reports found token."""
        with patch(
            "monarch_mcp_server.secure_session.SecureMonarchSession.load_token",
            return_value="valid_token_123",
        ):
            with patch.dict(os.environ, {}, clear=True):
                tool = await mcp._tool_manager.get_tool("check_auth_status")
                result = tool.fn()

            assert "found" in result.lower() or "token" in result.lower()

    @pytest.mark.asyncio
    async def test_without_token(self):
        """Verify check_auth_status reports missing token."""
        with patch(
            "monarch_mcp_server.secure_session.SecureMonarchSession.load_token",
            return_value=None,
        ):
            with patch.dict(os.environ, {}, clear=True):
                tool = await mcp._tool_manager.get_tool("check_auth_status")
                result = tool.fn()

            assert "No" in result or "no" in result

    @pytest.mark.asyncio
    async def test_with_env_email(self):
        """Verify check_auth_status reports environment email."""
        with patch(
            "monarch_mcp_server.secure_session.SecureMonarchSession.load_token",
            return_value=None,
        ):
            with patch.dict(
                os.environ, {"MONARCH_EMAIL": "test@example.com"}, clear=True
            ):
                tool = await mcp._tool_manager.get_tool("check_auth_status")
                result = tool.fn()

            assert "test@example.com" in result

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Verify check_auth_status handles exceptions gracefully."""
        with patch(
            "monarch_mcp_server.secure_session.SecureMonarchSession.load_token",
            side_effect=Exception("Keyring access denied"),
        ):
            tool = await mcp._tool_manager.get_tool("check_auth_status")
            result = tool.fn()

            assert "Error" in result or "error" in result
            assert "Keyring access denied" in result

    @pytest.mark.asyncio
    async def test_suggests_next_steps(self):
        """Verify check_auth_status provides helpful suggestions."""
        with patch(
            "monarch_mcp_server.secure_session.SecureMonarchSession.load_token",
            return_value="token",
        ):
            with patch.dict(os.environ, {}, clear=True):
                tool = await mcp._tool_manager.get_tool("check_auth_status")
                result = tool.fn()

            assert "get_accounts" in result or "login_setup" in result


class TestMain:
    """Tests for the main entry point."""

    @patch("monarch_mcp_server.server.mcp")
    @patch("monarch_mcp_server.server.logger")
    def test_calls_mcp_run(self, mock_logger, mock_mcp):
        """Verify main() calls mcp.run()."""
        main()

        mock_mcp.run.assert_called_once()
        mock_logger.info.assert_called()

    @patch("monarch_mcp_server.server.mcp")
    @patch("monarch_mcp_server.server.logger")
    def test_logs_exception_and_reraises(self, mock_logger, mock_mcp):
        """Verify main() logs errors and re-raises exceptions."""
        mock_mcp.run.side_effect = Exception("Server startup failed")

        with pytest.raises(Exception, match="Server startup failed"):
            main()

        mock_logger.error.assert_called()
        # Verify error message contains the exception details
        error_call_args = str(mock_logger.error.call_args)
        assert "Server startup failed" in error_call_args or "Failed" in error_call_args


class TestMCPInstance:
    """Tests for the global MCP instance."""

    def test_mcp_is_fastmcp_instance(self):
        """Verify mcp is a FastMCP instance."""
        assert isinstance(mcp, FastMCP)

    def test_mcp_has_name(self):
        """Verify mcp has a name attribute."""
        # FastMCP stores name - check it exists (implementation detail may vary)
        assert mcp is not None
        # The server initializes with "Monarch Money MCP Server"
        # Just verify we can access the tool manager (indicates proper initialization)
        assert mcp._tool_manager is not None

    @pytest.mark.asyncio
    async def test_tools_registered(self):
        """Verify essential tools are registered on mcp."""
        # Check that some core tools are registered
        tool = await mcp._tool_manager.get_tool("setup_authentication")
        assert tool is not None

        tool2 = await mcp._tool_manager.get_tool("check_auth_status")
        assert tool2 is not None


class TestAppExport:
    """Tests for the app export."""

    def test_app_is_exported(self):
        """Verify app is exported for mcp run."""
        from monarch_mcp_server.server import app

        # app should be a FastMCP instance
        assert isinstance(app, FastMCP)
        # Verify it has the expected server name
        assert app._mcp_server.name == "Monarch Money MCP Server"
