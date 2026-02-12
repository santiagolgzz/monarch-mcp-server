"""
Tool registry for Monarch Money MCP Server.

This module serves as the coordinator for all tool domain modules.
"""

import logging

from fastmcp import FastMCP

from .accounts import register_account_tools
from .budgets import register_budget_tools
from .categories import register_category_tools
from .metadata import register_metadata_tools
from .refresh import register_refresh_tools
from .safety import register_safety_tools
from .tags import register_tag_tools
from .transactions import register_transaction_tools

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP) -> None:
    """
    Register all Monarch Money tools with the provided FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with.
    """
    logger.info("Registering Monarch Money tools...")

    # Status & diagnostics first — agents should reach for these
    register_metadata_tools(mcp)
    register_safety_tools(mcp)

    # Core data (lightweight → heavyweight, reads → writes)
    register_transaction_tools(mcp)
    register_account_tools(mcp)
    register_budget_tools(mcp)
    register_category_tools(mcp)
    register_tag_tools(mcp)

    # Background operations last
    register_refresh_tools(mcp)

    logger.info("All Monarch Money tools registered.")


__all__ = ["register_tools"]
