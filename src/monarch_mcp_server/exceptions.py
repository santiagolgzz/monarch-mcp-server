"""Custom exceptions for Monarch MCP Server."""


class MonarchMCPError(Exception):
    """Base exception for all Monarch MCP Server errors."""

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class AuthenticationError(MonarchMCPError):
    """Raised when authentication fails or session is invalid."""

    def __init__(self, message: str = "Authentication required", details: str | None = None):
        super().__init__(message, details)


class SessionExpiredError(AuthenticationError):
    """Raised when the session has expired and needs refresh."""

    def __init__(self, details: str | None = None):
        super().__init__("Session expired. Please run login_setup.py to re-authenticate.", details)


class NetworkError(MonarchMCPError):
    """Raised when network communication fails."""

    def __init__(self, message: str = "Network error", details: str | None = None):
        super().__init__(message, details)


class APIError(MonarchMCPError):
    """Raised when the Monarch Money API returns an error."""

    def __init__(self, message: str, status_code: int | None = None, details: str | None = None):
        self.status_code = status_code
        super().__init__(message, details)


class ValidationError(MonarchMCPError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None, details: str | None = None):
        self.field = field
        super().__init__(message, details)


class SafetyError(MonarchMCPError):
    """Raised when a safety check blocks an operation."""

    def __init__(self, message: str = "Operation blocked by safety check", details: str | None = None):
        super().__init__(message, details)


class EmergencyStopError(SafetyError):
    """Raised when emergency stop is active."""

    def __init__(self):
        super().__init__(
            "🚨 EMERGENCY STOP ACTIVE: All write operations disabled.",
            "Use disable_emergency_stop to re-enable."
        )


