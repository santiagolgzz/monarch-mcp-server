"""Utility functions and decorators for Monarch MCP Server."""

import json
import logging
from typing import Any
from pathlib import Path

from .exceptions import (
    MonarchMCPError,
    AuthenticationError,
    NetworkError,
    APIError,
    ValidationError,
)

logger = logging.getLogger(__name__)


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


def validate_non_empty_string(value: str | None, field_name: str) -> str:
    """Validate that a string is not empty."""
    if not value or not value.strip():
        raise ValidationError(
            f"{field_name} cannot be empty",
            field=field_name
        )
    return value.strip()