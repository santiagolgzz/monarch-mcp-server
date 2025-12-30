"""Monarch Money MCP Server - Extended Edition.

An extended MCP server for Monarch Money with 40+ tools covering the complete API.
"""

__version__ = "1.1.0"

from monarch_mcp_server.exceptions import (
    MonarchMCPError,
    AuthenticationError,
    SessionExpiredError,
    NetworkError,
    APIError,
    ValidationError,
    SafetyError,
    EmergencyStopError,
)

from monarch_mcp_server.utils import (
    run_async,
    format_result,
    format_error,
    get_config_dir,
    get_config_path,
    validate_date_format,
)

from monarch_mcp_server.safety import (
    SafetyConfig,
    SafetyGuard,
    get_safety_guard,
    require_safety_check,
)

from monarch_mcp_server.secure_session import (
    SecureMonarchSession,
    secure_session,
)

__all__ = [
    # Version
    "__version__",
    # Exceptions
    "MonarchMCPError",
    "AuthenticationError",
    "SessionExpiredError",
    "NetworkError",
    "APIError",
    "ValidationError",
    "SafetyError",
    "EmergencyStopError",
    # Utils
    "run_async",
    "format_result",
    "format_error",
    "get_config_dir",
    "get_config_path",
    "validate_date_format",
    # Safety
    "SafetyConfig",
    "SafetyGuard",
    "get_safety_guard",
    "require_safety_check",
    # Session
    "SecureMonarchSession",
    "secure_session",
]