"""
Secure session management for Monarch Money MCP Server using keyring.
"""

import keyring
import logging
import os
from typing import Optional
from monarchmoney import MonarchMoney

logger = logging.getLogger(__name__)

# Keyring service identifiers
KEYRING_SERVICE = "com.mcp.monarch-mcp-server"
KEYRING_USERNAME = "monarch-token"


class SecureMonarchSession:
    """Manages Monarch Money sessions securely using the system keyring."""

    def save_token(self, token: str) -> None:
        """Save the authentication token to the system keyring."""
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, token)
            logger.info("✅ Token saved securely to keyring")

            # Clean up any old insecure files
            self._cleanup_old_session_files()

        except Exception as e:
            logger.error(f"❌ Failed to save token to keyring: {e}")
            raise

    def load_token(self) -> Optional[str]:
        """Load the authentication token from querying keyring or session file."""
        try:
            # 1. Try keyring first
            token = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            if token:
                logger.info("✅ Token loaded from keyring")
                return token
        except Exception as e:
            logger.error(f"❌ Failed to load token from keyring: {e}")

        # 2. Fallback to pickle file (standard library behavior)
        try:
            from pathlib import Path
            import pickle
            
            session_file = Path.home() / ".mm" / "mm_session.pickle"
            if session_file.exists():
                with open(session_file, "rb") as f:
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
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
            logger.info("🗑️ Token deleted from keyring")
        except Exception as e:
            error_type = type(e).__name__
            if "PasswordDeleteError" in error_type or "not found" in str(e).lower():
                logger.info("🔍 No token found in keyring to delete")
            else:
                logger.error(f"❌ Failed to delete token from keyring: {e}")

        # Also clean up session files
        self._cleanup_old_session_files()

        # Clean up the library's native session file too
        try:
            from pathlib import Path
            session_file = Path.home() / ".mm" / "mm_session.pickle"
            if session_file.exists():
                session_file.unlink()
                logger.info("🗑️ Deleted mm_session.pickle")
        except Exception as e:
            logger.error(f"❌ Failed to delete mm_session.pickle: {e}")

    def get_authenticated_client(self) -> Optional[MonarchMoney]:
        """Get an authenticated MonarchMoney client."""
        # First try to load session using library's native persistence (loads cookies!)
        mm = MonarchMoney()
        try:
            mm.load_session()
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
                mm.save_session()
                logger.info("✅ Full session (cookies) saved to mm_session.pickle")
            except Exception as e:
                logger.warning(f"⚠️ Could not save native session pickle: {e}")
        else:
            logger.warning("⚠️  MonarchMoney instance has no token to save")

    def _cleanup_old_session_files(self) -> None:
        """Clean up old insecure session files.
        
        Uses absolute paths based on user's home directory to avoid
        accidentally cleaning up files in wrong working directories.
        """
        from pathlib import Path
        
        home = Path.home()
        cleanup_paths = [
            # home / ".mm" / "mm_session.pickle",  <-- KEEP THIS ONE!
            home / "monarch_session.json",
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
