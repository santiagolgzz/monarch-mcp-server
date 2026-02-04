import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from fastmcp import FastMCP
from monarch_mcp_server.tools import register_tools

@pytest.fixture
def mcp():
    return FastMCP("test")

@pytest.mark.asyncio
async def test_get_accounts_async(mcp):
    """Verify get_accounts is registered and works asynchronously."""
    register_tools(mcp)
    
    mock_client = AsyncMock()
    mock_client.get_accounts.return_value = {"accounts": [{"id": "1", "displayName": "Test", "type": {"name": "checking"}, "currentBalance": 100, "institution": {"name": "Bank"}}]}
    
    with patch("monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client):
        tool = await mcp._tool_manager.get_tool("get_accounts")
        result = await tool.fn()
        
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["name"] == "Test"

@pytest.mark.asyncio
async def test_get_account_history_consistency(mcp):
    """Verify get_account_history return format is consistent."""
    register_tools(mcp)
    
    mock_client = AsyncMock()
    # Mock return from SDK
    mock_client.get_account_history.return_value = {"history": [{"date": "2024-01-01", "balance": 100}]}
    
    with patch("monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client):
        tool = await mcp._tool_manager.get_tool("get_account_history")
        # Test without filtering
        result = await tool.fn(account_id="1")
        data = json.loads(result)
        assert "history" in data
        assert len(data["history"]) == 1

@pytest.mark.asyncio
async def test_account_id_casting_safety(mcp):
    """Verify that passing an invalid account_id doesn't crash the server."""
    register_tools(mcp)
    
    mock_client = AsyncMock()
    with patch("monarch_mcp_server.tools.accounts.get_monarch_client", return_value=mock_client):
        tool = await mcp._tool_manager.get_tool("get_account_holdings")
        # Test with invalid ID
        result = await tool.fn(account_id="invalid")
        assert "error" in result.lower()
        assert "invalid account_id" in result.lower()