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
    """Compatibility wrapper that delegates to the shared decorator helper.

    The guard is looked up through a lambda rather than passed directly, so
    the lookup happens per call against this module's current attribute.
    Passing ``get_safety_guard`` itself bound the decorator to the original
    function at registration time, which meant patching
    ``monarch_mcp_server.safety.get_safety_guard`` had no effect on tools that
    were already registered — the seam existed to be patched, and wasn't.
    """
    return _require_safety(operation_name, lambda: get_safety_guard())
