import importlib
import os
from unittest.mock import patch

import pytest
from fastmcp import FastMCP


@pytest.mark.asyncio
async def test_http_server_registers_tools():
    """Verify that http_server.py registers tools using the shared module."""
    # Mock environment for GitHub OAuth
    env = {
        "GITHUB_CLIENT_ID": "test_id",
        "GITHUB_CLIENT_SECRET": "test_secret",
        "BASE_URL": "http://localhost:8000",
    }

    with patch.dict(os.environ, env):
        with patch("monarch_mcp_server.tools.register_tools") as mock_register:
            # Import and reload the module to trigger its setup code
            import monarch_mcp_server.http_server

            importlib.reload(monarch_mcp_server.http_server)

            # Check if mock_register was called
            mock_register.assert_called()
            args, kwargs = mock_register.call_args
            assert isinstance(args[0], FastMCP)
