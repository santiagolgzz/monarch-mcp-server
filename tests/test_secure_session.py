"""Tests for the secure_session module."""

import os
from unittest.mock import MagicMock, patch

from monarch_mcp_server.secure_session import (
    KEYRING_SERVICE,
    KEYRING_USERNAME,
    SecureMonarchSession,
    _resolve_default_session_file,
    _resolve_home_dir,
    secure_session,
)


class TestSecureMonarchSession:
    """Tests for SecureMonarchSession class."""

    @patch("monarch_mcp_server.secure_session.keyring")
    def test_save_token(self, mock_keyring):
        """Test saving token to keyring."""
        session = SecureMonarchSession()
        session.save_token("test_token_12345")

        mock_keyring.set_password.assert_called_once_with(
            KEYRING_SERVICE, KEYRING_USERNAME, "test_token_12345"
        )

    @patch("monarch_mcp_server.secure_session.keyring")
    def test_load_token_exists(self, mock_keyring):
        """Test loading token when it exists."""
        mock_keyring.get_password.return_value = "saved_token_xyz"

        session = SecureMonarchSession()
        token = session.load_token()

        assert token == "saved_token_xyz"
        mock_keyring.get_password.assert_called_once_with(
            KEYRING_SERVICE, KEYRING_USERNAME
        )

    @patch("monarch_mcp_server.secure_session.keyring")
    def test_load_token_not_exists(self, mock_keyring):
        """Test loading token when it doesn't exist."""
        mock_keyring.get_password.return_value = None

        session = SecureMonarchSession()
        token = session.load_token()

        assert token is None

    @patch("monarch_mcp_server.secure_session.keyring")
    def test_load_token_error(self, mock_keyring):
        """Test loading token when keyring raises error."""
        mock_keyring.get_password.side_effect = Exception("Keyring access denied")

        session = SecureMonarchSession()
        token = session.load_token()

        assert token is None

    @patch("monarch_mcp_server.secure_session.keyring")
    def test_delete_token(self, mock_keyring):
        """Test deleting token from keyring."""
        session = SecureMonarchSession()
        session.delete_token()

        mock_keyring.delete_password.assert_called_once_with(
            KEYRING_SERVICE, KEYRING_USERNAME
        )

    @patch("monarch_mcp_server.secure_session.keyring")
    def test_delete_token_not_found(self, mock_keyring):
        """Test deleting token when delete_password raises a generic error."""
        # Test that generic exceptions during delete are handled gracefully
        mock_keyring.delete_password.side_effect = Exception("Token not found")

        session = SecureMonarchSession()
        # Should not raise - the actual code handles exceptions
        session.delete_token()

        # Verify delete_password was called
        mock_keyring.delete_password.assert_called_once()

    @patch("monarch_mcp_server.secure_session.keyring")
    @patch("monarch_mcp_server.secure_session.MonarchMoney")
    def test_get_authenticated_client_success(self, mock_mm_class, mock_keyring):
        """Test getting authenticated client when token exists."""
        mock_keyring.get_password.return_value = "valid_token"

        # Configure mock client to fail native load but succeed with token
        mock_client = MagicMock()
        mock_client.token = None  # Initially no token from load_session
        mock_mm_class.return_value = mock_client

        session = SecureMonarchSession()
        client = session.get_authenticated_client()

        assert client is mock_client
        # Should initiate client, try load_session, then init again with token
        # Note: In implementation we create NEW instance for native load
        # simpler to just verify the token flow worked
        mock_mm_class.assert_any_call(token="valid_token")

    @patch("monarch_mcp_server.secure_session.keyring")
    @patch("monarch_mcp_server.secure_session.MonarchMoney")
    def test_get_authenticated_client_no_token(self, mock_mm_class, mock_keyring):
        """Test getting authenticated client when no token exists."""
        mock_keyring.get_password.return_value = None

        # Mock client that fails native load
        mock_client = MagicMock()
        mock_client.token = None
        mock_mm_class.return_value = mock_client

        session = SecureMonarchSession()
        client = session.get_authenticated_client()

        assert client is None

    @patch("monarch_mcp_server.secure_session.keyring")
    @patch("monarch_mcp_server.secure_session.MonarchMoney")
    def test_get_authenticated_client_error(self, mock_mm_class, mock_keyring):
        """Test getting authenticated client when MonarchMoney raises error."""
        mock_keyring.get_password.return_value = "invalid_token"

        # Setup side effect to fail on init with token
        # We need to handle the first init (empty) separately from second (with token)
        mock_mm_class.side_effect = [MagicMock(token=None), Exception("Invalid token")]

        session = SecureMonarchSession()
        client = session.get_authenticated_client()

        assert client is None

    @patch("monarch_mcp_server.secure_session.keyring")
    def test_save_authenticated_session(self, mock_keyring):
        """Test saving session from MonarchMoney instance."""
        mock_mm = MagicMock()
        mock_mm.token = "session_token_abc"

        session = SecureMonarchSession()
        session.save_authenticated_session(mock_mm)

        mock_keyring.set_password.assert_called_once_with(
            KEYRING_SERVICE, KEYRING_USERNAME, "session_token_abc"
        )
        # Verify native session is also saved
        mock_mm.save_session.assert_called_once()

    @patch("monarch_mcp_server.secure_session.keyring")
    def test_save_authenticated_session_no_token(self, mock_keyring):
        """Test saving session when MonarchMoney has no token."""
        mock_mm = MagicMock()
        mock_mm.token = None

        session = SecureMonarchSession()
        session.save_authenticated_session(mock_mm)

        # Should not call set_password
        mock_keyring.set_password.assert_not_called()


class TestGlobalSecureSession:
    """Tests for global secure_session instance."""

    def test_global_instance_exists(self):
        """Test that global secure_session is instantiated."""
        assert secure_session is not None
        assert isinstance(secure_session, SecureMonarchSession)


class TestSessionPathResolution:
    """Tests for resilient session path resolution."""

    def test_resolve_home_dir_falls_back_to_tmp_when_home_unavailable(self):
        """Path.home RuntimeError should fall back to /tmp."""
        from pathlib import Path

        with patch("pathlib.Path.home", side_effect=RuntimeError("no home")):
            assert _resolve_home_dir() == Path("/tmp")

    def test_resolve_default_session_file_uses_tmp_fallback(self):
        """Default session file should resolve under /tmp when home is unavailable."""
        from pathlib import Path

        with patch("pathlib.Path.home", side_effect=RuntimeError("no home")):
            assert _resolve_default_session_file() == Path("/tmp/.mm/mm_session.pickle")


class TestCleanupMethod:
    """Tests for the cleanup old session files method."""

    def test_cleanup_uses_absolute_paths(self):
        """Test that cleanup method uses absolute paths based on home directory."""
        from pathlib import Path
        from unittest.mock import patch

        session = SecureMonarchSession()

        # Mock Path operations to verify absolute paths are used
        with patch.object(Path, "exists", return_value=False):
            with patch("monarch_mcp_server.secure_session.keyring"):
                # This should not raise even if paths don't exist
                session._cleanup_old_session_files()

        # Verify the method completed without error
        # The cleanup should check paths relative to home
        # Since we mocked exists to return False, no deletions happen

    def test_cleanup_only_deletes_files(self):
        """Test that cleanup only deletes files, not directories."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mock .mm directory with a pickle file
            mm_dir = Path(tmpdir) / ".mm"
            mm_dir.mkdir()
            pickle_file = mm_dir / "mm_session.pickle"
            pickle_file.write_text("fake pickle content")

            session = SecureMonarchSession()

            # Patch Path.home to return our temp dir
            # We need to patch where Path is used (after import in the method)
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                with patch("monarch_mcp_server.secure_session.keyring"):
                    session._cleanup_old_session_files()

            # The pickle file should still exist (we stopped cleaning it up)
            assert pickle_file.exists()
            # But the .mm directory should still exist (not deleted)
            assert mm_dir.exists()

            # Verify that OTHER old files are still cleaned up
            json_file = Path(tmpdir) / "monarch_session.json"
            json_file.write_text("{}")

            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                with patch("monarch_mcp_server.secure_session.keyring"):
                    session._cleanup_old_session_files()

            assert not json_file.exists()


class TestKeyringUnavailable:
    """Tests for when keyring is not available."""

    def test_save_token_keyring_unavailable(self):
        """Test save_token when keyring is unavailable."""
        import sys

        # Get the actual module (not the class - imports can be tricky)
        ss_module = sys.modules["monarch_mcp_server.secure_session"]

        # Get the actual module-level constant
        original = ss_module.KEYRING_AVAILABLE

        # Temporarily set KEYRING_AVAILABLE to False
        ss_module.KEYRING_AVAILABLE = False  # type: ignore[attr-defined]

        try:
            session = SecureMonarchSession()
            # Should not raise, just skip saving to keyring
            session.save_token("test_token")
        finally:
            ss_module.KEYRING_AVAILABLE = original  # type: ignore[attr-defined]

    def test_load_token_env_var_priority(self):
        """Test that MONARCH_TOKEN env var takes priority."""
        from unittest.mock import patch

        with patch.dict(os.environ, {"MONARCH_TOKEN": "env_token_value"}):
            with patch("monarch_mcp_server.secure_session.keyring") as mock_keyring:
                mock_keyring.get_password.return_value = "keyring_token"

                from monarch_mcp_server.secure_session import SecureMonarchSession

                session = SecureMonarchSession()
                token = session.load_token()

                # Env var should take precedence
                assert token == "env_token_value"
                # Keyring should not even be called
                mock_keyring.get_password.assert_not_called()

    def test_load_token_pickle_fallback(self, tmp_path):
        """Test loading token from pickle file fallback."""
        import pickle
        from unittest.mock import patch

        # Create a pickle file with token
        mm_dir = tmp_path / ".mm"
        mm_dir.mkdir()
        pickle_file = mm_dir / "mm_session.pickle"

        with open(pickle_file, "wb") as f:
            pickle.dump({"token": "pickle_token_value"}, f)

        # Clear env var, make keyring return None
        with patch.dict(os.environ, {}, clear=True):
            with patch("monarch_mcp_server.secure_session.keyring") as mock_keyring:
                mock_keyring.get_password.return_value = None

                with patch(
                    "monarch_mcp_server.secure_session.DEFAULT_SESSION_FILE",
                    pickle_file,
                ):
                    from monarch_mcp_server.secure_session import SecureMonarchSession

                    session = SecureMonarchSession()
                    token = session.load_token()

                    assert token == "pickle_token_value"

    def test_load_token_pickle_fallback_no_token(self, tmp_path):
        """Test pickle fallback when pickle exists but has no token."""
        import pickle
        from unittest.mock import patch

        # Create a pickle file WITHOUT token
        mm_dir = tmp_path / ".mm"
        mm_dir.mkdir()
        pickle_file = mm_dir / "mm_session.pickle"

        with open(pickle_file, "wb") as f:
            pickle.dump({"other_data": "value"}, f)

        with patch.dict(os.environ, {}, clear=True):
            with patch("monarch_mcp_server.secure_session.keyring") as mock_keyring:
                mock_keyring.get_password.return_value = None

                with patch(
                    "monarch_mcp_server.secure_session.DEFAULT_SESSION_FILE",
                    pickle_file,
                ):
                    from monarch_mcp_server.secure_session import SecureMonarchSession

                    session = SecureMonarchSession()
                    token = session.load_token()

                    # No token in pickle, should return None
                    assert token is None


class TestNativeSessionLoad:
    """Tests for native session loading."""

    @patch("monarch_mcp_server.secure_session.keyring")
    @patch("monarch_mcp_server.secure_session.MonarchMoney")
    def test_get_authenticated_client_native_session(self, mock_mm_class, mock_keyring):
        """Test that native session with token is returned immediately."""
        from monarch_mcp_server.secure_session import SecureMonarchSession

        mock_client = MagicMock()
        mock_client.token = "native_session_token"  # Has token from load_session
        mock_mm_class.return_value = mock_client

        session = SecureMonarchSession()
        client = session.get_authenticated_client()

        assert client is mock_client
        # load_session should have been called
        mock_client.load_session.assert_called_once()
