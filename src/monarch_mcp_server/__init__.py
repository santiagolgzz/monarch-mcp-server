"""Monarch Money MCP Server - Extended Edition.

An extended MCP server for Monarch Money with 40+ tools covering the complete API.
"""

__version__ = "1.1.0"

from monarchmoney import MonarchMoneyEndpoints

# PATCH: Monarch Money rebranded from monarchmoney.com to monarch.com
# The library hasn't been updated yet (as of v0.1.15), so we monkey-patch the BASE_URL
# See: https://github.com/hammem/monarchmoney/issues/184
MonarchMoneyEndpoints.BASE_URL = "https://api.monarch.com"

from monarch_mcp_server.exceptions import (  # noqa: E402
    APIError,
    AuthenticationError,
    EmergencyStopError,
    MonarchMCPError,
    NetworkError,
    SafetyError,
    SessionExpiredError,
    ValidationError,
)
from monarch_mcp_server.safety import (  # noqa: E402
    SafetyConfig,
    SafetyGuard,
    get_safety_guard,
    require_safety_check,
)
from monarch_mcp_server.secure_session import (  # noqa: E402
    SecureMonarchSession,
    secure_session,
)
from monarch_mcp_server.utils import (  # noqa: E402
    format_error,
    format_result,
    get_config_dir,
    get_config_path,
    validate_date_format,
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
