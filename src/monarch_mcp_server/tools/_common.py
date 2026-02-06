"""
Common utilities for Monarch Money tools.

Contains shared decorator and constants used across all tool modules.
"""

import functools
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
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Decorator that wraps tool functions with error handling.

    This decorator:
    1. Catches all exceptions and formats them using format_error()
    2. Returns native Python objects so MCP can build typed structured content

    Args:
        operation_name: Name of the operation for error messages and logging.

    Returns:
        Decorated function that preserves the wrapped function's return type.

    Example:
        @mcp.tool()
        @require_safety_check("create_tag")  # Safety first (for write ops)
        @tool_handler("create_tag")          # Error handling innermost
        async def create_tag(name: str) -> dict:
            client = await get_monarch_client()
            return await client.create_transaction_tag(name=name)
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Failed in {operation_name}: {e}")
                # Propagate as an exception so MCP surfaces it as a tool error
                # rather than attempting to validate an incompatible return shape.
                raise RuntimeError(format_error(e, operation_name)) from e

        return wrapper

    return decorator
