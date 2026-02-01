"""Utility functions and decorators for Monarch MCP Server."""

import asyncio
import json
import logging
import functools
from typing import Any, Callable, TypeVar, ParamSpec
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from .exceptions import (
    MonarchMCPError,
    AuthenticationError,
    NetworkError,
    APIError,
    ValidationError,
)

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

# Persistent thread pool for async operations
_executor: ThreadPoolExecutor | None = None


def get_executor() -> ThreadPoolExecutor:
    """Get or create the persistent thread pool executor."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="monarch_async_")
    return _executor


def shutdown_executor() -> None:
    """Shutdown the thread pool executor gracefully."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None


def run_async(coro: Any) -> Any:
    """
    Run async function efficiently using a persistent thread pool.
    
    This is more efficient than creating a new event loop for each call.
    """
    def _run() -> Any:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    executor = get_executor()
    future = executor.submit(_run)
    return future.result()


def get_config_dir() -> Path:
    """Get the configuration directory path, creating it if needed."""
    # Use user's home directory for cross-platform compatibility
    config_dir = Path.home() / ".mm"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path(filename: str) -> Path:
    """Get full path to a configuration file."""
    return get_config_dir() / filename


def classify_exception(e: Exception) -> MonarchMCPError:
    """
    Classify a generic exception into a specific MonarchMCPError type.
    
    This helps provide better error messages to users.
    """
    error_str = str(e).lower()
    error_type = type(e).__name__
    
    # Authentication errors
    if any(term in error_str for term in ["auth", "login", "credential", "token", "session"]):
        if "expired" in error_str:
            from .exceptions import SessionExpiredError
            return SessionExpiredError(str(e))
        return AuthenticationError(details=str(e))
    
    # Network errors
    if any(term in error_str for term in ["connection", "timeout", "network", "dns", "refused"]):
        return NetworkError(details=str(e))
    
    if "ClientError" in error_type or "HTTPError" in error_type:
        return NetworkError(details=str(e))
    
    # API errors
    if any(term in error_str for term in ["api", "invalid", "not found", "400", "404", "500"]):
        return APIError(str(e))
    
    # Validation errors
    if any(term in error_str for term in ["validation", "invalid", "required", "missing"]):
        return ValidationError(str(e))
    
    # Default to generic error
    return MonarchMCPError(str(e))


def format_result(data: Any) -> str:
    """Format result data as JSON string."""
    return json.dumps(data, indent=2, default=str)


def format_error(error: Exception, operation: str) -> str:
    """
    Format an error message for user display with actionable suggestions.

    Analyzes the error and provides specific guidance on how to resolve it.
    """
    error_str = str(error)
    error_lower = error_str.lower()

    # Build suggestion based on error type
    suggestion = ""

    # 401 Unauthorized - session expired
    if "401" in error_str or "unauthorized" in error_lower:
        suggestion = "\n\n💡 FIX: Your session has expired. Run `python login_setup.py` to re-authenticate."

    # Parameter mismatch errors (common when API changes)
    elif "unexpected keyword argument" in error_lower:
        # Extract the bad parameter name
        import re
        match = re.search(r"'(\w+)'", error_str)
        bad_param = match.group(1) if match else "unknown"
        suggestion = f"\n\n💡 FIX: The parameter '{bad_param}' is not accepted by the Monarch API. Check the tool's required parameters using introspection."

    elif "missing" in error_lower and "required" in error_lower:
        suggestion = "\n\n💡 FIX: A required parameter is missing. Use tool introspection to see all required parameters."

    # Network/connection errors
    elif any(term in error_lower for term in ["connection", "timeout", "network", "refused"]):
        suggestion = "\n\n💡 FIX: Network error. Check your internet connection and try again."

    # Rate limiting
    elif "rate limit" in error_lower or "too many requests" in error_lower:
        suggestion = "\n\n💡 FIX: Rate limit exceeded. Wait a moment before trying again. Use `get_safety_stats` to check current limits."

    # Validation errors
    elif "validation" in error_lower or "invalid" in error_lower:
        if "date" in error_lower:
            suggestion = "\n\n💡 FIX: Use date format YYYY-MM-DD (e.g., 2025-12-31)."
        elif "amount" in error_lower:
            suggestion = "\n\n💡 FIX: Amount should be a number. Positive for income, negative for expenses."
        else:
            suggestion = "\n\n💡 FIX: Check that all parameters have valid values."

    # Not found errors
    elif "not found" in error_lower or "404" in error_str:
        suggestion = "\n\n💡 FIX: The requested resource was not found. Verify the ID exists using the appropriate get_* tool."

    # Format the final message
    if isinstance(error, MonarchMCPError):
        base_msg = f"Error in {operation}: {error}"
    else:
        classified = classify_exception(error)
        base_msg = f"Error in {operation}: {classified}"

    return base_msg + suggestion


def monarch_tool(operation_name: str | None = None) -> Callable[[Callable[P, T]], Callable[P, str]]:
    """
    Decorator to reduce boilerplate in MCP tool functions.
    
    Handles:
    - Running async code
    - JSON formatting of results
    - Error classification and logging
    - Consistent error message format
    
    Args:
        operation_name: Optional name for the operation (defaults to function name)
    
    Usage:
        @mcp.tool()
        @monarch_tool("get_accounts")
        async def get_accounts():
            client = await get_monarch_client()
            return await client.get_accounts()
    """
    def decorator(func: Callable[P, T]) -> Callable[P, str]:
        name = operation_name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
            try:
                # Check if the function is async
                if asyncio.iscoroutinefunction(func):
                    result = run_async(func(*args, **kwargs))
                else:
                    result = func(*args, **kwargs)
                
                return format_result(result)
            
            except MonarchMCPError as e:
                logger.error(f"Failed in {name}: {e}")
                return format_error(e, name)
            
            except Exception as e:
                logger.error(f"Failed in {name}: {e}")
                return format_error(e, name)
        
        return wrapper
    
    return decorator


def validate_date_format(date_str: str | None, field_name: str = "date") -> str | None:
    """
    Validate that a date string is in YYYY-MM-DD format.
    
    Returns the date string if valid, raises ValidationError if invalid.
    """
    if date_str is None:
        return None
    
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValidationError(
            f"Invalid date format for {field_name}. Expected YYYY-MM-DD, got: {date_str}",
            field=field_name
        )
    
    return date_str


def validate_positive_amount(amount: float, field_name: str = "amount") -> float:
    """Validate that an amount is positive."""
    if amount <= 0:
        raise ValidationError(
            f"{field_name} must be positive, got: {amount}",
            field=field_name
        )
    return amount


def validate_non_empty_string(value: str | None, field_name: str) -> str:
    """Validate that a string is not empty."""
    if not value or not value.strip():
        raise ValidationError(
            f"{field_name} cannot be empty",
            field=field_name
        )
    return value.strip()
