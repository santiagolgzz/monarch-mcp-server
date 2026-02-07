"""Safety module facade for Monarch MCP Server."""

from monarch_mcp_server.safety_config import SafetyConfig
from monarch_mcp_server.safety_decorator import require_safety_check as _require_safety
from monarch_mcp_server.safety_guard import SafetyGuard

__all__ = ["SafetyConfig", "SafetyGuard", "get_safety_guard", "require_safety_check"]

# Global instance - eagerly initialized to avoid race conditions in async context
_safety_guard = SafetyGuard()


def get_safety_guard() -> SafetyGuard:
    """Get the global safety guard instance."""
    return _safety_guard


def require_safety_check(operation_name: str):
    """Compatibility wrapper that delegates to the shared decorator helper."""
    return _require_safety(operation_name, get_safety_guard)
