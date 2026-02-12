"""
Common utilities for Monarch Money tools.

Contains shared decorator and constants used across all tool modules.
"""

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from monarch_mcp_server.exceptions import AuthenticationError
from monarch_mcp_server.secure_session import secure_session
from monarch_mcp_server.utils import format_error

logger = logging.getLogger(__name__)

# Constants
MAX_AGGREGATION_TRANSACTIONS = 2000
"""Maximum number of transactions to fetch for aggregation operations."""


# Type variables for the decorator
P = ParamSpec("P")
T = TypeVar("T")


def _is_auth_error(e: Exception) -> bool:
    """Check if an exception indicates an expired/invalid Monarch session."""
    if isinstance(e, AuthenticationError):
        return True
    err = str(e).lower()
    return "401" in err or "unauthorized" in err


def tool_handler(
    operation_name: str,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Decorator that wraps tool functions with error handling and session auto-retry.

    This decorator:
    1. Catches all exceptions and formats them using format_error()
    2. On auth/session errors, invalidates the cached session and retries once
    3. Returns native Python objects so MCP can build typed structured content

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
                return await func(*args, **kwargs)
            except Exception as e:
                if _is_auth_error(e):
                    logger.warning(
                        f"Auth error in {operation_name}, "
                        "invalidating session and retrying..."
                    )
                    secure_session.delete_token()
                    try:
                        return await func(*args, **kwargs)
                    except Exception as retry_err:
                        logger.error(f"Retry failed in {operation_name}: {retry_err}")
                        raise RuntimeError(
                            format_error(retry_err, operation_name)
                        ) from retry_err

                logger.error(f"Failed in {operation_name}: {e}")
                raise RuntimeError(format_error(e, operation_name)) from e

        return wrapper

    return decorator
