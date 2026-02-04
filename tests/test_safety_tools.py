"""Tests for safety management tools."""

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


@pytest.mark.asyncio
async def test_get_recent_operations_no_log_file(mcp, tmp_path):
    """Verify get_recent_operations handles missing log file gracefully."""
    register_tools(mcp)

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_recent_operations")
        result = await tool.fn(limit=10)

        data = json.loads(result)
        assert data["operations"] == []
        assert "No operations" in data["message"] or data["count"] == 0


@pytest.mark.asyncio
async def test_get_recent_operations_limit_capped_at_50(mcp, tmp_path):
    """Verify get_recent_operations caps limit at 50."""
    register_tools(mcp)

    # Create log file with many entries
    log_dir = tmp_path / ".mm"
    log_dir.mkdir()
    log_file = log_dir / "detailed_operation_log.jsonl"

    ops = [
        json.dumps({"operation": f"op_{i}", "timestamp": f"2024-01-01T12:{i:02d}:00Z"})
        for i in range(60)
    ]
    log_file.write_text("\n".join(ops) + "\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_recent_operations")
        # Request 100, should be capped to 50
        result = await tool.fn(limit=100)

        data = json.loads(result)
        assert data["count"] <= 50


@pytest.mark.asyncio
async def test_get_recent_operations_skips_invalid_json(mcp, tmp_path):
    """Verify get_recent_operations skips lines with invalid JSON."""
    register_tools(mcp)

    log_dir = tmp_path / ".mm"
    log_dir.mkdir()
    log_file = log_dir / "detailed_operation_log.jsonl"

    # Mix valid and invalid JSON lines
    content = (
        json.dumps({"operation": "valid_1"})
        + "\n"
        + "this is not valid json\n"
        + json.dumps({"operation": "valid_2"})
        + "\n"
    )
    log_file.write_text(content)

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_recent_operations")
        result = await tool.fn(limit=10)

        data = json.loads(result)
        # Should have 2 valid operations, skipping the invalid line
        assert data["count"] == 2


@pytest.mark.asyncio
async def test_get_recent_operations_empty_file(mcp, tmp_path):
    """Verify get_recent_operations handles empty log file."""
    register_tools(mcp)

    log_dir = tmp_path / ".mm"
    log_dir.mkdir()
    log_file = log_dir / "detailed_operation_log.jsonl"
    log_file.write_text("")

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_recent_operations")
        result = await tool.fn(limit=10)

        data = json.loads(result)
        assert data["count"] == 0
        assert data["operations"] == []


@pytest.mark.asyncio
async def test_get_rollback_suggestions_no_log_file(mcp, tmp_path):
    """Verify get_rollback_suggestions handles missing log file."""
    register_tools(mcp)

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_rollback_suggestions")
        result = await tool.fn(operation_index=0)

        assert "No operations logged" in result


@pytest.mark.asyncio
async def test_get_rollback_suggestions_invalid_index(mcp, tmp_path):
    """Verify get_rollback_suggestions handles invalid operation index."""
    register_tools(mcp)

    log_dir = tmp_path / ".mm"
    log_dir.mkdir()
    log_file = log_dir / "detailed_operation_log.jsonl"

    # Only one operation
    log_file.write_text(
        json.dumps({"operation": "create", "timestamp": "2024-01-01"}) + "\n"
    )

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_rollback_suggestions")
        result = await tool.fn(operation_index=10)

        assert "not found" in result.lower() or "Only" in result


@pytest.mark.asyncio
async def test_get_rollback_suggestions_json_decode_error(mcp, tmp_path):
    """Verify get_rollback_suggestions handles invalid JSON in log file."""
    register_tools(mcp)

    log_dir = tmp_path / ".mm"
    log_dir.mkdir()
    log_file = log_dir / "detailed_operation_log.jsonl"
    log_file.write_text("not valid json\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_rollback_suggestions")
        result = await tool.fn(operation_index=0)

        assert "Failed to parse" in result or "error" in result.lower()


@pytest.mark.asyncio
async def test_get_rollback_suggestions_deleted_id(mcp, tmp_path):
    """Verify get_rollback_suggestions shows deleted_id rollback info."""
    register_tools(mcp)

    log_dir = tmp_path / ".mm"
    log_dir.mkdir()
    log_file = log_dir / "detailed_operation_log.jsonl"

    op = {
        "operation": "delete_transaction",
        "timestamp": "2024-01-01T12:00:00Z",
        "parameters": {"transaction_id": "txn_123"},
        "rollback_info": {
            "reversible": True,
            "reverse_operation": "create_transaction",
            "notes": "Recreate the deleted transaction",
            "deleted_id": "txn_123",
        },
    }
    log_file.write_text(json.dumps(op) + "\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_rollback_suggestions")
        result = await tool.fn(operation_index=0)

        assert "REVERSIBLE" in result
        assert "txn_123" in result
        assert "Deleted ID" in result


@pytest.mark.asyncio
async def test_get_rollback_suggestions_created_id(mcp, tmp_path):
    """Verify get_rollback_suggestions shows created_id rollback info."""
    register_tools(mcp)

    log_dir = tmp_path / ".mm"
    log_dir.mkdir()
    log_file = log_dir / "detailed_operation_log.jsonl"

    op = {
        "operation": "create_transaction",
        "timestamp": "2024-01-01T12:00:00Z",
        "parameters": {"amount": 50.0},
        "rollback_info": {
            "reversible": True,
            "reverse_operation": "delete_transaction",
            "notes": "Delete the created transaction",
            "created_id": "new_txn_456",
        },
    }
    log_file.write_text(json.dumps(op) + "\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_rollback_suggestions")
        result = await tool.fn(operation_index=0)

        assert "REVERSIBLE" in result
        assert "new_txn_456" in result
        assert "Created ID" in result


@pytest.mark.asyncio
async def test_get_rollback_suggestions_modified_id(mcp, tmp_path):
    """Verify get_rollback_suggestions shows modified_id rollback info."""
    register_tools(mcp)

    log_dir = tmp_path / ".mm"
    log_dir.mkdir()
    log_file = log_dir / "detailed_operation_log.jsonl"

    op = {
        "operation": "update_transaction",
        "timestamp": "2024-01-01T12:00:00Z",
        "parameters": {"transaction_id": "txn_789", "amount": 100.0},
        "rollback_info": {
            "reversible": True,
            "reverse_operation": "update_transaction",
            "notes": "Restore original values",
            "modified_id": "txn_789",
            "modified_fields": {"amount": 50.0},
        },
    }
    log_file.write_text(json.dumps(op) + "\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_rollback_suggestions")
        result = await tool.fn(operation_index=0)

        assert "REVERSIBLE" in result
        assert "txn_789" in result
        assert "Modified ID" in result
        assert "amount" in result


@pytest.mark.asyncio
async def test_get_rollback_suggestions_non_reversible(mcp, tmp_path):
    """Verify get_rollback_suggestions handles non-reversible operations."""
    register_tools(mcp)

    log_dir = tmp_path / ".mm"
    log_dir.mkdir()
    log_file = log_dir / "detailed_operation_log.jsonl"

    op = {
        "operation": "bulk_delete",
        "timestamp": "2024-01-01T12:00:00Z",
        "parameters": {"ids": ["1", "2", "3"]},
        "rollback_info": {
            "reversible": False,
            "notes": "Cannot undo bulk delete",
        },
    }
    log_file.write_text(json.dumps(op) + "\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_rollback_suggestions")
        result = await tool.fn(operation_index=0)

        assert "NOT EASILY REVERSIBLE" in result
        assert "cannot be easily reversed" in result.lower()


@pytest.mark.asyncio
async def test_enable_emergency_stop_tool(mcp):
    """Verify enable_emergency_stop calls safety guard."""
    register_tools(mcp)

    with patch("monarch_mcp_server.tools.safety.get_safety_guard") as mock_guard:
        mock_guard.return_value.enable_emergency_stop.return_value = (
            "Emergency stop enabled"
        )

        tool = await mcp._tool_manager.get_tool("enable_emergency_stop")
        result = await tool.fn()

        assert "Emergency stop enabled" in result
        mock_guard.return_value.enable_emergency_stop.assert_called_once()


@pytest.mark.asyncio
async def test_disable_emergency_stop_tool(mcp):
    """Verify disable_emergency_stop calls safety guard."""
    register_tools(mcp)

    with patch("monarch_mcp_server.tools.safety.get_safety_guard") as mock_guard:
        mock_guard.return_value.disable_emergency_stop.return_value = (
            "Emergency stop disabled"
        )

        tool = await mcp._tool_manager.get_tool("disable_emergency_stop")
        result = await tool.fn()

        assert "Emergency stop disabled" in result
        mock_guard.return_value.disable_emergency_stop.assert_called_once()


@pytest.mark.asyncio
async def test_get_rollback_suggestions_deleted_ids(mcp, tmp_path):
    """Verify get_rollback_suggestions shows deleted_ids (plural) rollback info."""
    register_tools(mcp)

    log_dir = tmp_path / ".mm"
    log_dir.mkdir()
    log_file = log_dir / "detailed_operation_log.jsonl"

    op = {
        "operation": "delete_categories",
        "timestamp": "2024-01-01T12:00:00Z",
        "parameters": {"category_ids": "cat_1,cat_2"},
        "rollback_info": {
            "reversible": True,
            "reverse_operation": "create_categories",
            "notes": "Recreate the deleted categories",
            "deleted_ids": ["cat_1", "cat_2"],
        },
    }
    log_file.write_text(json.dumps(op) + "\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        tool = await mcp._tool_manager.get_tool("get_rollback_suggestions")
        result = await tool.fn(operation_index=0)

        assert "REVERSIBLE" in result
        assert "cat_1" in result
        assert "cat_2" in result
        assert "2 deleted items" in result
