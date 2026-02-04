"""
Safety management tools for Monarch Money.

Tools for monitoring and controlling write operation safety.
"""

import json
import logging
from collections import deque
from pathlib import Path

from fastmcp import FastMCP

from monarch_mcp_server.safety import get_safety_guard

from ._common import tool_handler

logger = logging.getLogger(__name__)


def register_safety_tools(mcp: FastMCP) -> None:
    """Register safety management tools with the FastMCP instance."""

    @mcp.tool()
    @tool_handler("get_safety_stats")
    async def get_safety_stats() -> dict:
        """Get current safety statistics including daily operation counts and emergency stop status."""
        guard = get_safety_guard()
        return guard.get_operation_stats()

    @mcp.tool()
    @tool_handler("enable_emergency_stop")
    async def enable_emergency_stop() -> str:
        """EMERGENCY: Disable all write operations immediately."""
        guard = get_safety_guard()
        return guard.enable_emergency_stop()

    @mcp.tool()
    @tool_handler("disable_emergency_stop")
    async def disable_emergency_stop() -> str:
        """Re-enable write operations after emergency stop."""
        guard = get_safety_guard()
        return guard.disable_emergency_stop()

    @mcp.tool()
    @tool_handler("get_recent_operations")
    async def get_recent_operations(limit: int = 10) -> dict:
        """View recent write operations with rollback information."""
        limit = min(limit, 50)  # Cap at 50
        detailed_log_path = Path.home() / ".mm" / "detailed_operation_log.jsonl"

        if not detailed_log_path.exists():
            return {"message": "No operations logged yet", "operations": []}

        # Read last N lines using collections.deque (efficient for large files)
        operations = []
        with open(detailed_log_path) as f:
            # deque(f, maxlen=limit) efficiently reads only the last lines
            last_lines = deque(f, maxlen=limit)
            for line in last_lines:
                try:
                    operations.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Reverse to show most recent first
        operations.reverse()

        return {
            "count": len(operations),
            "operations": operations,
            "log_file": str(detailed_log_path),
        }

    @mcp.tool()
    @tool_handler("get_rollback_suggestions")
    async def get_rollback_suggestions(operation_index: int = 0) -> str:
        """Get detailed rollback suggestions for a recent operation."""
        detailed_log_path = Path.home() / ".mm" / "detailed_operation_log.jsonl"

        if not detailed_log_path.exists():
            return "No operations logged yet."

        # Read operations efficiently
        # We need at least operation_index + 1 lines from the end
        with open(detailed_log_path) as f:
            # deque(f, maxlen=operation_index + 1) reads only what's needed
            last_lines = deque(f, maxlen=operation_index + 1)

            if len(last_lines) <= operation_index:
                return f"Operation index {operation_index} not found. Only {len(last_lines)} operations logged."

            # The requested operation is the first in our deque
            target_line = last_lines[0]
            op = json.loads(target_line)

        # Generate rollback suggestions
        rollback = op.get("rollback_info", {})
        params = op.get("parameters", {})

        suggestion = f"""Rollback Information

Timestamp: {op.get("timestamp")}
Operation: {op.get("operation")}
Parameters: {json.dumps(params, indent=2)}

{"REVERSIBLE" if rollback.get("reversible") else "NOT EASILY REVERSIBLE"}

"""

        if rollback.get("reversible"):
            suggestion += f"""Reverse Operation: {rollback.get("reverse_operation")}
Instructions: {rollback.get("notes")}

"""
            if "deleted_id" in rollback:
                suggestion += f"To undo: Recreate the deleted item using its original details\n   Deleted ID: {rollback['deleted_id']}\n"
            elif "deleted_ids" in rollback:
                suggestion += f"To undo: Recreate {len(rollback['deleted_ids'])} deleted items\n   Deleted IDs: {', '.join(rollback['deleted_ids'])}\n"
            elif "created_id" in rollback:
                suggestion += f"To undo: Delete the created item\n   Created ID: {rollback['created_id']}\n"
            elif "modified_id" in rollback and "modified_fields" in rollback:
                suggestion += f"To undo: Restore original values\n   Modified ID: {rollback['modified_id']}\n   Changed fields: {', '.join(rollback['modified_fields'].keys())}\n"
        else:
            suggestion += "This operation cannot be easily reversed.\n   You may need to manually fix any issues in Monarch Money web interface.\n"

        return suggestion
