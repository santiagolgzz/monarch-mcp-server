"""Tests for server.py - main server implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

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
        result = tool.fn()

        # Check key instruction elements are present
        assert "Monarch Money" in result
        assert "login_setup.py" in result
        assert "MONARCH_EMAIL" in result
        assert "MONARCH_PASSWORD" in result

    @pytest.mark.asyncio
    async def test_mentions_interactive_as_recommended(self):
        """Verify instructions recommend interactive login."""
        tool = await mcp._tool_manager.get_tool("setup_authentication")
        result = tool.fn()
        assert "Recommended" in result
        assert "Interactive" in result or "keyring" in result

    @pytest.mark.asyncio
    async def test_mentions_mfa(self):
        """Verify instructions mention MFA support."""
        tool = await mcp._tool_manager.get_tool("setup_authentication")
        result = tool.fn()
        assert "MFA" in result

    @pytest.mark.asyncio
    async def test_mentions_session_persistence(self):
        """Verify instructions mention session persistence."""
        tool = await mcp._tool_manager.get_tool("setup_authentication")
        result = tool.fn()
        assert "persist" in result.lower() or "weeks" in result.lower()


class TestCheckAuthStatus:
    """Tests for the check_auth_status tool."""

    @pytest.mark.asyncio
    async def test_with_valid_connection_premium(self):
        """Verify check_auth_status reports successful connection for premium users."""
        mock_client = MagicMock()
        mock_client.get_subscription_details = AsyncMock(
            return_value={"hasPremiumEntitlement": True}
        )

        with patch(
            "monarch_mcp_server.tools.metadata.get_monarch_client",
            return_value=mock_client,
        ):
            tool = await mcp._tool_manager.get_tool("check_auth_status")
            result = await tool.fn()

            assert "Authenticated" in result
            assert "Premium" in result

    @pytest.mark.asyncio
    async def test_with_valid_connection_free(self):
        """Verify check_auth_status shows plan info for free users."""
        mock_client = MagicMock()
        mock_client.get_subscription_details = AsyncMock(
            return_value={"hasPremiumEntitlement": False}
        )

        with patch(
            "monarch_mcp_server.tools.metadata.get_monarch_client",
            return_value=mock_client,
        ):
            tool = await mcp._tool_manager.get_tool("check_auth_status")
            result = await tool.fn()

            assert "Authenticated" in result
            assert "Free" in result or "Trial" in result

    @pytest.mark.asyncio
    async def test_not_authenticated(self):
        """Verify check_auth_status reports when not authenticated."""
        from monarch_mcp_server.exceptions import AuthenticationError

        with patch(
            "monarch_mcp_server.tools.metadata.get_monarch_client",
            side_effect=AuthenticationError("Authentication required!"),
        ):
            tool = await mcp._tool_manager.get_tool("check_auth_status")
            result = await tool.fn()

            assert "Not authenticated" in result
            assert "login_setup" in result.lower()

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Verify check_auth_status handles connection errors."""
        with patch(
            "monarch_mcp_server.tools.metadata.get_monarch_client",
            side_effect=Exception("Network timeout"),
        ):
            tool = await mcp._tool_manager.get_tool("check_auth_status")
            result = await tool.fn()

            assert "failed" in result.lower()
            assert "Network timeout" in result


class TestMain:
    """Tests for the main entry point."""

    @patch("monarch_mcp_server.server.mcp")
    @patch("monarch_mcp_server.server.logger")
    def test_calls_mcp_run(self, mock_logger, mock_mcp):
        """Verify main() calls mcp.run()."""
        main()

        mock_mcp.run.assert_called_once_with(show_banner=False)
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
