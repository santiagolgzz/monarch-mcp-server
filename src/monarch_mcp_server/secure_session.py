"""
Secure session management for Monarch Money MCP Server using keyring.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from monarchmoney import MonarchMoney, MonarchMoneyEndpoints

# Try to import keyring, but make it optional for container deployments
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

logger = logging.getLogger(__name__)

# Keyring service identifiers
# Keyring service identifiers
KEYRING_SERVICE = "com.mcp.monarch-mcp-server"
KEYRING_USERNAME = "monarch-token"

# Standardize session file location to user's home directory
DEFAULT_SESSION_FILE = Path.home() / ".mm" / "mm_session.pickle"


class SecureMonarchSession:
    """Manages Monarch Money sessions securely using the system keyring."""

    def save_token(self, token: str) -> None:
        """Save the authentication token to the system keyring."""
        if not KEYRING_AVAILABLE:
            logger.info("⏭️ Keyring not available, skipping token save to keyring")
            return

        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, token)
            logger.info("✅ Token saved securely to keyring")

            # Clean up any old insecure files
            self._cleanup_old_session_files()

        except Exception as e:
            logger.warning(f"⚠️ Failed to save token to keyring: {e}")

    def load_token(self) -> Optional[str]:
        """Load the authentication token from environment, keyring, or session file.

        Priority order:
        1. MONARCH_TOKEN environment variable (for cloud deployment)
        2. System keyring (for local use)
        3. Pickle file fallback (legacy support)
        """
        # 1. Try environment variable first (for cloud/container deployment)
        env_token = os.getenv("MONARCH_TOKEN")
        if env_token:
            logger.info("✅ Token loaded from MONARCH_TOKEN environment variable")
            return env_token

        if KEYRING_AVAILABLE:
            try:
                # 2. Try keyring second (local use)
                token = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
                if token:
                    logger.info("✅ Token loaded from keyring")
                    return token
            except Exception as e:
                logger.warning(f"⚠️ Failed to load token from keyring: {e}")

        # 2. Fallback to pickle file (standard library behavior)
        try:
            import pickle
            
            if DEFAULT_SESSION_FILE.exists():
                with open(DEFAULT_SESSION_FILE, "rb") as f:
                    data = pickle.load(f)
                    token = data.get("token")
                    if token:
                        logger.info("✅ Token loaded from mm_session.pickle fallback")
                        return token
        except Exception as e:
            logger.error(f"❌ Failed to load token from session file: {e}")

        logger.info("🔍 No token found in keyring or session file")
        return None

    def delete_token(self) -> None:
        """Delete the authentication token from system keyring and session file."""
        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
                logger.info("🗑️ Token deleted from keyring")
            except Exception as e:
                error_type = type(e).__name__
                if "PasswordDeleteError" in error_type or "not found" in str(e).lower():
                    logger.info("🔍 No token found in keyring to delete")
                else:
                    logger.warning(f"⚠️ Failed to delete token from keyring: {e}")

        # Also clean up session files
        self._cleanup_old_session_files()

        # Clean up the library's native session file too
        try:
            if DEFAULT_SESSION_FILE.exists():
                DEFAULT_SESSION_FILE.unlink()
                logger.info(f"🗑️ Deleted {DEFAULT_SESSION_FILE}")
        except Exception as e:
            logger.error(f"❌ Failed to delete mm_session.pickle: {e}")

    def get_authenticated_client(self) -> Optional[MonarchMoney]:
        """Get an authenticated MonarchMoney client."""
        # First try to load session using library's native persistence (loads cookies!)
        mm = MonarchMoney()
        try:
            # Explicitly use the default session file path
            mm.load_session(filename=str(DEFAULT_SESSION_FILE))
            if mm.token:
                logger.info("✅ MonarchMoney client loaded with native session (cookies+token)")
                return mm
        except Exception as e:
            logger.warning(f"⚠️ Failed to load native session: {e}")

        # Fallback to token-only auth (from keyring) if native load failed
        token = self.load_token()
        if token:
            try:
                client = MonarchMoney(token=token)
                logger.info("✅ MonarchMoney client created with stored token (token-only)")
                return client
            except Exception as e:
                logger.error(f"❌ Failed to create MonarchMoney client: {e}")
        
        return None

    def save_authenticated_session(self, mm: MonarchMoney) -> None:
        """Save the session from an authenticated MonarchMoney instance."""
        if mm.token:
            # 1. Save to keyring (most secure)
            self.save_token(mm.token)
            
            # 2. Save native session pickle (persists cookies for long sessions)
            try:
                # Be sure to create the directory if it doesn't exist
                DEFAULT_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
                mm.save_session(filename=str(DEFAULT_SESSION_FILE))
                logger.info(f"✅ Full session (cookies) saved to {DEFAULT_SESSION_FILE}")
            except Exception as e:
                logger.warning(f"⚠️ Could not save native session pickle: {e}")
        else:
            logger.warning("⚠️  MonarchMoney instance has no token to save")

    def _cleanup_old_session_files(self) -> None:
        """Clean up old insecure session files.
        
        Uses absolute paths based on user's home directory to avoid
        accidentally cleaning up files in wrong working directories.
        """
        
        cleanup_paths = [
            # home / ".mm" / "mm_session.pickle",  <-- KEEP THIS ONE! (Handled by delete_token now)
            Path.home() / "monarch_session.json",
        ]

        for path in cleanup_paths:
            try:
                if path.exists() and path.is_file():
                    path.unlink()
                    logger.info(f"🗑️ Cleaned up old insecure session file: {path}")
            except Exception as e:
                logger.warning(f"⚠️  Could not clean up {path}: {e}")


# Global session manager instance
secure_session = SecureMonarchSession()
