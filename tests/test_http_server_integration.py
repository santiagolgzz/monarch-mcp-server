import os
from unittest.mock import patch

import pytest
from fastmcp import FastMCP


@pytest.mark.asyncio
async def test_http_server_registers_tools():
    """Verify that http_server.py registers tools when creating the MCP server."""
    # Mock environment for GitHub OAuth
    env = {
        "MCP_AUTH_MODE": "oauth",
        "GITHUB_CLIENT_ID": "test_id",
        "GITHUB_CLIENT_SECRET": "test_secret",
        "MCP_OAUTH_REDIS_URL": "redis://localhost:6379/0",
        "MCP_OAUTH_JWT_SIGNING_KEY": "integration-test-signing-key",
        "BASE_URL": "http://localhost:8000",
    }

    with patch.dict(os.environ, env):
        # Patch at the location where it's imported/used
        with patch("monarch_mcp_server.http_server.register_tools") as mock_register:
            from monarch_mcp_server.http_server import create_mcp_server

            create_mcp_server()

            # Check if mock_register was called
            mock_register.assert_called()
            args, kwargs = mock_register.call_args
            assert isinstance(args[0], FastMCP)
