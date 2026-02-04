import json
from unittest.mock import AsyncMock, patch

import pytest


class TestDestructiveToolsInServer:
    """Tests for destructive tool implementations using registered tools."""

    @pytest.mark.asyncio
    async def test_delete_transaction_allowed_no_emergency_stop(self):
        """Test delete_transaction is allowed when not in emergency stop."""
        from fastmcp import FastMCP

        from monarch_mcp_server.safety import get_safety_guard
        from monarch_mcp_server.tools import register_tools

        mcp = FastMCP("test")
        register_tools(mcp)

        guard = get_safety_guard()
        original_stop = guard.config.config.get("emergency_stop", False)
        guard.config.config["emergency_stop"] = False

        try:
            # We need to mock get_monarch_client to avoid actual API calls
            with patch(
                "monarch_mcp_server.tools.transactions.get_monarch_client"
            ) as mock_client:
                mock_client.return_value.delete_transaction = AsyncMock()

                tool = await mcp._tool_manager.get_tool("delete_transaction")
                result = await tool.fn(transaction_id="txn_123")

                # Should not be blocked
                assert "blocked" not in result.lower()
        finally:
            guard.config.config["emergency_stop"] = original_stop

    @pytest.mark.asyncio
    async def test_delete_transaction_blocked_by_emergency_stop(self):
        """Test delete_transaction is blocked during emergency stop."""
        from fastmcp import FastMCP

        from monarch_mcp_server.safety import get_safety_guard
        from monarch_mcp_server.tools import register_tools

        mcp = FastMCP("test")
        register_tools(mcp)

        guard = get_safety_guard()
        original_stop = guard.config.config.get("emergency_stop", False)
        guard.config.config["emergency_stop"] = True

        try:
            tool = await mcp._tool_manager.get_tool("delete_transaction")
            result = await tool.fn(transaction_id="txn_123")

            result_data = json.loads(result)
            assert "error" in result_data
            assert "blocked" in result_data["error"].lower()
            assert "EMERGENCY STOP" in result_data["reason"]
        finally:
            guard.config.config["emergency_stop"] = original_stop

    @pytest.mark.asyncio
    async def test_delete_account_blocked_by_emergency_stop(self):
        """Test delete_account is blocked during emergency stop."""
        from fastmcp import FastMCP

        from monarch_mcp_server.safety import get_safety_guard
        from monarch_mcp_server.tools import register_tools

        mcp = FastMCP("test")
        register_tools(mcp)

        guard = get_safety_guard()
        original_stop = guard.config.config.get("emergency_stop", False)
        guard.config.config["emergency_stop"] = True

        try:
            tool = await mcp._tool_manager.get_tool("delete_account")
            result = await tool.fn(account_id="acc_123")

            result_data = json.loads(result)
            assert "error" in result_data
            assert "blocked" in result_data["error"].lower()
        finally:
            guard.config.config["emergency_stop"] = original_stop
