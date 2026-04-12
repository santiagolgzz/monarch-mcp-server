"""
Secure session management for Monarch Money MCP Server.

Uses the system keyring when available, with an automatic file-based
fallback for environments without a keyring backend (e.g. WSL, headless Linux).
"""

import logging
import os
import stat
from pathlib import Path

from monarchmoney import MonarchMoney

from monarch_mcp_server.paths import mm_file, resolve_home_dir

logger = logging.getLogger(__name__)

# Keyring service identifiers
KEYRING_SERVICE = "com.mcp.monarch-mcp-server"
KEYRING_USERNAME = "monarch-token"

# File-based fallback token path (uses ~/.mm/ with /tmp fallback)
_TOKEN_FILE = mm_file("token")


def _keyring_available() -> bool:
    """Check whether a usable keyring backend is available.

    Detects fake/null backends common on WSL and headless Linux,
    and performs a round-trip probe for ChainerBackend.
    """
    try:
        import keyring

        backend = keyring.get_keyring()
        backend_name = type(backend).__name__

        # These backends indicate no real keyring is available
        if backend_name in ("Keyring", "NullKeyring", "FailKeyring", "ChainerBackend"):
            # ChainerBackend may wrap a real backend — try a round-trip test
            if backend_name == "ChainerBackend":
                try:
                    keyring.set_password(KEYRING_SERVICE, "__probe__", "1")
                    keyring.delete_password(KEYRING_SERVICE, "__probe__")
                    return True
                except Exception:
                    return False
            return False
        return True
    except Exception:
        return False


def _resolve_default_session_file() -> Path:
    """Compute default session file path with a safe fallback."""
    return mm_file("mm_session.pickle")


# Standardize session file location with fallback for restricted runtimes
DEFAULT_SESSION_FILE = _resolve_default_session_file()


class SecureMonarchSession:
    """Manages Monarch Money sessions securely using the system keyring,
    falling back to a file-based store when no keyring backend is available."""

    def __init__(self) -> None:
        self._use_keyring = _keyring_available()
        if self._use_keyring:
            logger.info("Using system keyring for token storage")
        else:
            logger.info("Keyring unavailable — using file-based token storage")

    # -- file-based helpers --------------------------------------------------

    def _save_token_file(self, token: str) -> None:
        """Save token to file with owner-only permissions (0o600)."""
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(token)
        _TOKEN_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
        logger.info(f"Token saved to {_TOKEN_FILE}")

    def _load_token_file(self) -> str | None:
        """Load token from file fallback."""
        if _TOKEN_FILE.is_file():
            token = _TOKEN_FILE.read_text().strip()
            if token:
                logger.info(f"Token loaded from {_TOKEN_FILE}")
                return token
        return None

    def _delete_token_file(self) -> None:
        """Delete the file-based token if it exists."""
        if _TOKEN_FILE.is_file():
            _TOKEN_FILE.unlink()
            logger.info(f"Token file deleted: {_TOKEN_FILE}")

    # -- public API ----------------------------------------------------------

    def save_token(self, token: str) -> bool:
        """Save the authentication token to keyring or file fallback.

        Returns:
            True if token was saved successfully, False otherwise.
        """
        if self._use_keyring:
            try:
                import keyring

                keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, token)
                logger.info("Token saved securely to keyring")
                self._cleanup_old_session_files()
                return True
            except Exception as e:
                logger.warning(f"Keyring save failed, falling back to file: {e}")

        try:
            self._save_token_file(token)
            self._cleanup_old_session_files()
            return True
        except Exception as e:
            logger.error(f"Failed to save token to file: {e}")
            return False

    def load_token(self) -> str | None:
        """Load the authentication token.

        Priority order:
        1. MONARCH_TOKEN environment variable (for cloud deployment)
        2. System keyring (if available)
        3. File-based token (~/.mm/token)
        4. Legacy session file (fallback)
        """
        # 1. Environment variable (cloud/container deployment)
        env_token = os.getenv("MONARCH_TOKEN")
        if env_token:
            logger.info("Token loaded from MONARCH_TOKEN environment variable")
            return env_token

        # 2. System keyring
        if self._use_keyring:
            try:
                import keyring

                token = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
                if token:
                    logger.info("Token loaded from keyring")
                    return token
            except Exception as e:
                logger.warning(f"Failed to load token from keyring: {e}")

        # 3. File-based token
        token = self._load_token_file()
        if token:
            return token

        # 4. Legacy session file fallback (MonarchMoney SDK format)
        try:
            if DEFAULT_SESSION_FILE.exists():
                mm = MonarchMoney()
                mm.load_session(filename=str(DEFAULT_SESSION_FILE))
                if mm.token:
                    logger.info("Token loaded from native session file fallback")
                    return mm.token
        except Exception as e:
            logger.error(f"Failed to load token from session file: {e}")

        logger.info("No token found in any storage backend")
        return None

    def delete_token(self) -> None:
        """Delete the authentication token from all storage backends."""
        # Skip destructive cleanup when using ephemeral env tokens
        if os.getenv("MONARCH_TOKEN"):
            logger.info("MONARCH_TOKEN env var set — skipping stored token cleanup")
            return

        # Try keyring
        if self._use_keyring:
            try:
                import keyring

                keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
                logger.info("Token deleted from keyring")
            except Exception:
                pass

        # Try file
        self._delete_token_file()

        # Clean up legacy session files
        self._cleanup_old_session_files()

        # Clean up native session file
        try:
            if DEFAULT_SESSION_FILE.exists():
                DEFAULT_SESSION_FILE.unlink()
                logger.info(f"Deleted {DEFAULT_SESSION_FILE}")
        except Exception as e:
            logger.error(f"Failed to delete session file: {e}")

    def get_authenticated_client(self) -> MonarchMoney | None:
        """Get an authenticated MonarchMoney client.

        Priority:
        1. MONARCH_TOKEN env var (overrides everything)
        2. Native session file (cookies + token)
        3. Stored token (keyring -> file -> legacy)
        """
        # 1. Env token takes absolute priority
        env_token = os.getenv("MONARCH_TOKEN")
        if env_token:
            try:
                client = MonarchMoney(token=env_token)
                logger.info("Client created with MONARCH_TOKEN env var")
                return client
            except Exception as e:
                logger.warning(f"Failed to create client from MONARCH_TOKEN: {e}")
                # Fall through to other methods

        # 2. Try native session (preserves cookies for longer sessions)
        mm = MonarchMoney()
        try:
            mm.load_session(filename=str(DEFAULT_SESSION_FILE))
            if mm.token:
                logger.info(
                    "MonarchMoney client loaded with native session (cookies+token)"
                )
                return mm
        except Exception as e:
            logger.warning(f"Failed to load native session: {e}")

        # 3. Fall back to stored token (keyring/file)
        token = self.load_token()
        if token:
            try:
                client = MonarchMoney(token=token)
                logger.info("MonarchMoney client created with stored token")
                return client
            except Exception as e:
                logger.error(f"Failed to create MonarchMoney client: {e}")

        return None

    def save_authenticated_session(self, mm: MonarchMoney) -> None:
        """Save the session from an authenticated MonarchMoney instance."""
        if mm.token:
            # 1. Save token to keyring/file (most secure)
            self.save_token(mm.token)

            # 2. Save native session (persists cookies for long sessions)
            try:
                DEFAULT_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
                mm.save_session(filename=str(DEFAULT_SESSION_FILE))
                logger.info(f"Full session (cookies) saved to {DEFAULT_SESSION_FILE}")
            except Exception as e:
                logger.warning(f"Could not save native session: {e}")
        else:
            logger.warning("MonarchMoney instance has no token to save")

    def _cleanup_old_session_files(self) -> None:
        """Clean up old insecure session files."""
        cleanup_paths = [
            resolve_home_dir() / "monarch_session.json",
        ]

        for path in cleanup_paths:
            try:
                if path.exists() and path.is_file():
                    path.unlink()
                    logger.info(f"Cleaned up old insecure session file: {path}")
            except Exception as e:
                logger.warning(f"Could not clean up {path}: {e}")


# Global session manager instance
secure_session = SecureMonarchSession()
