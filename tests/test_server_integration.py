import importlib
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_server_registers_tools():
    """Verify that server.py main logic registers tools using the shared module."""
    with patch("monarch_mcp_server.tools.register_tools") as mock_register:
        # Import and reload the module to trigger its setup code
        import monarch_mcp_server.server

        importlib.reload(monarch_mcp_server.server)

        # Check if the global mcp instance was passed to register_tools
        from monarch_mcp_server.server import mcp

        mock_register.assert_called_with(mcp)
