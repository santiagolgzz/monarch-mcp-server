"""
Common utilities for Monarch Money tools.

Contains shared decorator and constants used across all tool modules.
"""

import functools
import json
import logging
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from monarch_mcp_server.utils import format_error

logger = logging.getLogger(__name__)

# Constants
MAX_AGGREGATION_TRANSACTIONS = 2000
"""Maximum number of transactions to fetch for aggregation operations."""


# Type variables for the decorator
P = ParamSpec("P")
T = TypeVar("T")


def tool_handler(
    operation_name: str,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[str]]]:
    """
    Decorator that wraps tool functions with error handling and JSON serialization.

    This decorator:
    1. Catches all exceptions and formats them using format_error()
    2. Serializes dict/list results to JSON with indent=2
    3. Passes through string results unchanged (already formatted)

    Args:
        operation_name: Name of the operation for error messages and logging.

    Returns:
        Decorated function that returns a JSON string.

    Example:
        @mcp.tool()
        @require_safety_check("create_tag")  # Safety first (for write ops)
        @tool_handler("create_tag")          # Error handling innermost
        async def create_tag(name: str) -> dict:
            client = await get_monarch_client()
            return await client.create_transaction_tag(name=name)
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[str]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
            try:
                result = await func(*args, **kwargs)
                # Pass through strings (already formatted)
                if isinstance(result, str):
                    return result
                # Serialize dicts/lists to JSON
                return json.dumps(result, indent=2, default=str)
            except Exception as e:
                logger.error(f"Failed in {operation_name}: {e}")
                return format_error(e, operation_name)

        return wrapper

    return decorator
