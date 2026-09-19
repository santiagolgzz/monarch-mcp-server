"""
Safety management tools for Monarch Money.

Tools for monitoring and controlling write operation safety.
"""

import json
import logging
from collections import deque

from fastmcp import FastMCP

from monarch_mcp_server.paths import mm_file
from monarch_mcp_server.safety import get_safety_guard

from ._common import tool_handler

logger = logging.getLogger(__name__)


def _format_args(arguments: dict) -> str:
    """Render reverse-call arguments as a copy-pasteable argument list."""
    return ", ".join(f"{key}={value!r}" for key, value in arguments.items())


def register_safety_tools(mcp: FastMCP) -> None:
    """Register safety management tools with the FastMCP instance."""

    @mcp.tool()
    @tool_handler("get_safety_stats")
    async def get_safety_stats() -> dict:
        """Get current safety statistics including daily operation counts and emergency stop status."""
        guard = get_safety_guard()
        return guard.get_operation_stats()

    @mcp.tool()
    @tool_handler("get_recent_operations")
    async def get_recent_operations(limit: int = 10) -> dict:
        """View recent write operations with rollback information."""
        limit = min(limit, 50)  # Cap at 50
        detailed_log_path = mm_file("detailed_operation_log.jsonl")

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
        detailed_log_path = mm_file("detailed_operation_log.jsonl")

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
            try:
                op = json.loads(target_line)
            except json.JSONDecodeError:
                return "Failed to parse operation log entry: invalid JSON."

        rollback = op.get("rollback_info", {})
        params = op.get("parameters", {})

        lines = [
            "Rollback Information",
            "",
            f"Timestamp: {op.get('timestamp')}",
            f"Operation: {op.get('operation')}",
            f"Succeeded: {op.get('success', True)}",
            f"Parameters: {json.dumps(params, indent=2)}",
            "",
        ]

        if op.get("error"):
            lines += [f"Error: {op['error']}", ""]

        call = rollback.get("reverse_call") or {}

        if rollback.get("reversible") and call.get("tool"):
            lines += [
                "REVERSIBLE",
                "",
                rollback.get("notes", ""),
                "",
                "Run this to undo it:",
                "",
                f"  {call['tool']}({_format_args(call.get('arguments', {}))})",
                "",
            ]
        elif rollback.get("reversible"):
            # An entry written before rollback plans carried a reverse call.
            # Those logs claimed reversibility without recording what an undo
            # would need, so the honest answer is what was kept, not a
            # fabricated call.
            lines += [
                "REVERSIBLE — but no reverse call was recorded",
                "",
                "This entry predates executable rollback plans, so the data "
                "needed to undo it may not have been captured. What was "
                "recorded:",
                "",
                json.dumps(
                    {
                        key: value
                        for key, value in rollback.items()
                        if key
                        not in ("reversible", "reverse_operation", "reverse_call")
                    },
                    indent=2,
                    default=str,
                ),
                "",
            ]
        else:
            # Say exactly what is missing. "Not easily reversible" told the
            # caller nothing and read as a soft maybe.
            lines += [
                "NOT REVERSIBLE FROM THIS LOG",
                "",
                rollback.get("blocked_reason")
                or "No rollback plan was recorded for this operation.",
                "",
            ]
            if rollback.get("pre_state"):
                lines += [
                    "The snapshot below was captured before the operation ran "
                    "and may help you restore it by hand:",
                    "",
                    json.dumps(rollback["pre_state"], indent=2),
                    "",
                ]

        return "\n".join(lines)

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
