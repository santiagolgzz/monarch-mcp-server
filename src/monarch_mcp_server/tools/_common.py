"""
Common utilities for Monarch Money tools.

Contains shared decorator and constants used across all tool modules.
"""

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from monarch_mcp_server.exceptions import AuthenticationError
from monarch_mcp_server.secure_session import secure_session
from monarch_mcp_server.utils import format_error

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Constants
MAX_AGGREGATION_TRANSACTIONS = 2000
"""Maximum number of transactions to fetch for aggregation operations."""

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
"""Maximum decoded size of a transaction attachment upload (10 MiB).

Attachments arrive base64-encoded over MCP, which inflates them by about a
third, so the limit is checked against the decoded bytes."""


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
        @annotated_tool(mcp)
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


def annotated_tool(mcp: "FastMCP"):
    """Register a tool, declaring its MCP annotations.

    Used in place of a bare ``@mcp.tool()`` so no tool can reach a client
    without behaviour hints. A client that cannot tell `delete_account` from
    `get_accounts` cannot put a person in front of the difference, and this
    server's own confirmation gate can't either — it runs in-band and never
    learns whether a human saw it.

    Hints are derived from the tag ``require_safety_check`` leaves on its
    wrapper, so this restates nothing about which operations write or destroy.
    Place it outermost, above ``@require_safety_check``::

        @annotated_tool(mcp)
        @require_safety_check("delete_transaction")
        @tool_handler("delete_transaction")
        async def delete_transaction(...): ...
    """
    from monarch_mcp_server.annotations import annotations_for_function

    def decorator(func):
        return mcp.tool(annotations=annotations_for_function(func))(func)

    return decorator
