import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools


@pytest.fixture
async def mcp():
    mcp_instance = FastMCP("test")
    register_tools(mcp_instance)
    return mcp_instance


@pytest.mark.asyncio
async def test_get_transactions_validates_date_format(mcp):
    """Test that get_transactions validates date format."""
    # Invalid date format should return validation error
    tool = await mcp._tool_manager.get_tool("get_transactions")
    with pytest.raises(RuntimeError, match="Invalid date format"):
        await tool.fn(start_date="01-15-2024")


@pytest.mark.asyncio
async def test_create_transaction_validates_required_fields(mcp):
    """Test that create_transaction validates required fields."""
    # Empty account_id should fail validation
    tool = await mcp._tool_manager.get_tool("create_transaction")
    with pytest.raises(RuntimeError, match="account_id cannot be empty"):
        await tool.fn(
            account_id="",
            amount=50.0,
            merchant_name="Test Merchant",
            category_id="cat_123",
            date="2024-01-15",
        )


@pytest.mark.asyncio
async def test_update_transaction_validates_date_if_provided(mcp):
    """Test that update_transaction validates date format when provided."""
    # Invalid date format should fail validation
    tool = await mcp._tool_manager.get_tool("update_transaction")
    with pytest.raises(RuntimeError, match="Invalid date format"):
        await tool.fn(transaction_id="txn_123", date="bad-date-format")
