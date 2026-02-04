from fastmcp import FastMCP


def test_register_tools_exists():
    """Verify that register_tools function exists in tools module."""
    from monarch_mcp_server.tools import register_tools

    assert callable(register_tools)


def test_register_tools_accepts_mcp():
    """Verify that register_tools accepts an mcp instance."""
    from monarch_mcp_server.tools import register_tools

    mcp = FastMCP("test")
    # This should not raise an exception even if it does nothing yet
    register_tools(mcp)
