"""Shared path helpers for runtime-safe Monarch MCP file locations."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def resolve_home_dir() -> Path:
    """Resolve home directory safely for restricted runtimes."""
    try:
        return Path.home()
    except RuntimeError:
        logger.warning(
            "Could not resolve user home directory; falling back to /tmp "
            "for Monarch MCP data files."
        )
        return Path("/tmp")


def mm_data_dir() -> Path:
    """Get Monarch MCP data directory, creating it if needed."""
    config_dir = resolve_home_dir() / ".mm"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def mm_file(name: str) -> Path:
    """Get full path for a file under the Monarch MCP data directory."""
    return mm_data_dir() / name
