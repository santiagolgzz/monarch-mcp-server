import json
from unittest.mock import patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.mark.asyncio
async def test_get_safety_stats_async(mcp):
    """Verify get_safety_stats is registered and works asynchronously."""
    register_tools(mcp)

    with patch("monarch_mcp_server.tools.safety.get_safety_guard") as mock_guard:
        mock_guard.return_value.get_operation_stats.return_value = {"daily_count": 5}

        tool = await mcp._tool_manager.get_tool("get_safety_stats")
        result = await tool.fn()

        data = json.loads(result)
        assert data["daily_count"] == 5


@pytest.mark.asyncio
async def test_get_recent_operations_optimized(mcp, tmp_path):
    """Verify get_recent_operations is optimized and reads from log file."""
    register_tools(mcp)

    # Create a fake log file
    log_dir = tmp_path / ".mm"
    log_dir.mkdir()
    log_file = log_dir / "detailed_operation_log.jsonl"

    ops = [
        json.dumps({"operation": "create", "timestamp": "2024-01-01T12:00:00Z"}),
        json.dumps({"operation": "update", "timestamp": "2024-01-01T12:05:00Z"}),
    ]
    log_file.write_text("\n".join(ops) + "\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_recent_operations")
        result = await tool.fn(limit=1)

        data = json.loads(result)
        assert data["count"] == 1
        assert data["operations"][0]["operation"] == "update"
