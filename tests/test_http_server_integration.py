import os
from unittest.mock import patch

import pytest
from fastmcp import FastMCP


@pytest.mark.asyncio
async def test_http_server_registers_tools():
    """Verify that http_server.py registers tools when creating the app."""
    # Mock environment for GitHub OAuth
    env = {
        "GITHUB_CLIENT_ID": "test_id",
        "GITHUB_CLIENT_SECRET": "test_secret",
        "BASE_URL": "http://localhost:8000",
    }

    with patch.dict(os.environ, env):
        # Patch at the location where it's imported/used
        with patch("monarch_mcp_server.http_server.register_tools") as mock_register:
            # Import the function and call it - app is now lazy-loaded
            from monarch_mcp_server.http_server import create_app

            # create_app triggers create_mcp_server which registers tools
            create_app()

            # Check if mock_register was called
            mock_register.assert_called()
            args, kwargs = mock_register.call_args
            assert isinstance(args[0], FastMCP)
