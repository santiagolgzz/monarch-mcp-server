"""Tests for the secure_session module."""

import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

from monarch_mcp_server.secure_session import (
    KEYRING_SERVICE,
    KEYRING_USERNAME,
    SecureMonarchSession,
    _keyring_available,
    _resolve_default_session_file,
    secure_session,
)


class TestKeyringAvailable:
    """Tests for the _keyring_available() backend detection function."""

    def test_returns_false_for_null_keyring(self):
        mock_backend = MagicMock()
        type(mock_backend).__name__ = "NullKeyring"
        with patch("keyring.get_keyring", return_value=mock_backend):
            assert _keyring_available() is False

    def test_returns_false_for_fail_keyring(self):
        mock_backend = MagicMock()
        type(mock_backend).__name__ = "FailKeyring"
        with patch("keyring.get_keyring", return_value=mock_backend):
            assert _keyring_available() is False

    def test_returns_true_for_real_backend(self):
        mock_backend = MagicMock()
        type(mock_backend).__name__ = "SecretServiceKeyring"
        with patch("keyring.get_keyring", return_value=mock_backend):
            assert _keyring_available() is True

    def test_returns_true_for_macos_keyring(self):
        """macOS uses keyring.backends.macOS.Keyring — must not be rejected."""
        mock_backend = MagicMock()
        type(mock_backend).__name__ = "Keyring"
        with patch("keyring.get_keyring", return_value=mock_backend):
            assert _keyring_available() is True

    def test_probes_chainer_backend_success(self):
        mock_backend = MagicMock()
        type(mock_backend).__name__ = "ChainerBackend"
        with (
            patch("keyring.get_keyring", return_value=mock_backend),
            patch("keyring.set_password"),
            patch("keyring.delete_password"),
        ):
            assert _keyring_available() is True

    def test_probes_chainer_backend_failure(self):
        mock_backend = MagicMock()
        type(mock_backend).__name__ = "ChainerBackend"
        with (
            patch("keyring.get_keyring", return_value=mock_backend),
            patch("keyring.set_password", side_effect=Exception("no backend")),
        ):
            assert _keyring_available() is False

    def test_returns_false_when_keyring_not_installed(self):
        with patch.dict("sys.modules", {"keyring": None}):
            assert _keyring_available() is False


class TestSecureMonarchSession:
    """Tests for SecureMonarchSession class."""

    def _make_session(self, use_keyring=True):
        """Create a session with controlled keyring availability."""
        with patch(
            "monarch_mcp_server.secure_session._keyring_available",
            return_value=use_keyring,
        ):
            return SecureMonarchSession()

    def test_save_token_to_keyring(self):
        session = self._make_session(use_keyring=True)
        with patch("keyring.set_password") as mock_set:
            result = session.save_token("test_token_12345")

        assert result is True
        mock_set.assert_called_once_with(
            KEYRING_SERVICE, KEYRING_USERNAME, "test_token_12345"
        )

    def test_save_token_keyring_fails_falls_back_to_file(self, tmp_path):
        session = self._make_session(use_keyring=True)
        token_file = tmp_path / "token"

        with (
            patch("keyring.set_password", side_effect=Exception("keyring broken")),
            patch("monarch_mcp_server.secure_session._TOKEN_FILE", token_file),
        ):
            result = session.save_token("fallback_token")

        assert result is True
        assert token_file.read_text() == "fallback_token"
        assert token_file.stat().st_mode & 0o777 == stat.S_IRUSR | stat.S_IWUSR

    def test_save_token_file_fallback_when_no_keyring(self, tmp_path):
        session = self._make_session(use_keyring=False)
        token_file = tmp_path / "token"

        with patch("monarch_mcp_server.secure_session._TOKEN_FILE", token_file):
            result = session.save_token("file_token")

        assert result is True
        assert token_file.read_text() == "file_token"

    def test_save_token_file_permissions_600(self, tmp_path):
        session = self._make_session(use_keyring=False)
        token_file = tmp_path / "token"

        with patch("monarch_mcp_server.secure_session._TOKEN_FILE", token_file):
            session.save_token("secret")

        mode = token_file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_load_token_from_keyring(self):
        session = self._make_session(use_keyring=True)
        with patch("keyring.get_password", return_value="keyring_token"):
            token = session.load_token()

        assert token == "keyring_token"

    def test_load_token_keyring_empty_falls_to_file(self, tmp_path):
        session = self._make_session(use_keyring=True)
        token_file = tmp_path / "token"
        token_file.write_text("file_token")

        with (
            patch("keyring.get_password", return_value=None),
            patch("monarch_mcp_server.secure_session._TOKEN_FILE", token_file),
        ):
            token = session.load_token()

        assert token == "file_token"

    def test_load_token_returns_none_when_all_empty(self, tmp_path):
        session = self._make_session(use_keyring=True)
        token_file = tmp_path / "nonexistent_token"

        with (
            patch("keyring.get_password", return_value=None),
            patch("monarch_mcp_server.secure_session._TOKEN_FILE", token_file),
            patch(
                "monarch_mcp_server.secure_session.DEFAULT_SESSION_FILE",
                tmp_path / "nonexistent.session",
            ),
        ):
            token = session.load_token()

        assert token is None

    def test_load_token_keyring_error_falls_through(self, tmp_path):
        session = self._make_session(use_keyring=True)
        token_file = tmp_path / "token"
        token_file.write_text("fallback_token")

        with (
            patch("keyring.get_password", side_effect=Exception("broken")),
            patch("monarch_mcp_server.secure_session._TOKEN_FILE", token_file),
        ):
            token = session.load_token()

        assert token == "fallback_token"

    def test_delete_token_from_keyring(self):
        session = self._make_session(use_keyring=True)
        with patch("keyring.delete_password") as mock_del:
            session.delete_token()

        mock_del.assert_called_once_with(KEYRING_SERVICE, KEYRING_USERNAME)

    def test_delete_token_cleans_file(self, tmp_path):
        session = self._make_session(use_keyring=False)
        token_file = tmp_path / "token"
        token_file.write_text("to_delete")

        with patch("monarch_mcp_server.secure_session._TOKEN_FILE", token_file):
            session.delete_token()

        assert not token_file.exists()

    def test_delete_token_skips_when_env_token_set(self):
        session = self._make_session(use_keyring=True)
        with (
            patch.dict(os.environ, {"MONARCH_TOKEN": "env_tok"}),
            patch("keyring.delete_password") as mock_del,
        ):
            session.delete_token()

        mock_del.assert_not_called()

    @patch("monarch_mcp_server.secure_session.MonarchMoney")
    def test_get_authenticated_client_with_keyring_token(self, mock_mm_class):
        session = self._make_session(use_keyring=True)
        mock_client = MagicMock()
        mock_client.token = None  # native load fails
        mock_token_client = MagicMock()
        mock_mm_class.side_effect = [mock_client, mock_token_client]

        with patch("keyring.get_password", return_value="keyring_tok"):
            client = session.get_authenticated_client()

        assert client is mock_token_client
        mock_mm_class.assert_any_call(token="keyring_tok")

    @patch("monarch_mcp_server.secure_session.MonarchMoney")
    def test_get_authenticated_client_no_token(self, mock_mm_class):
        session = self._make_session(use_keyring=True)
        mock_client = MagicMock()
        mock_client.token = None
        mock_mm_class.return_value = mock_client

        with (
            patch("keyring.get_password", return_value=None),
            patch(
                "monarch_mcp_server.secure_session.DEFAULT_SESSION_FILE",
                Path("/tmp/nonexistent.session"),
            ),
            patch(
                "monarch_mcp_server.secure_session._TOKEN_FILE",
                Path("/tmp/nonexistent_token"),
            ),
        ):
            client = session.get_authenticated_client()

        assert client is None

    def test_save_authenticated_session(self):
        session = self._make_session(use_keyring=True)
        mock_mm = MagicMock()
        mock_mm.token = "session_token_abc"

        with patch("keyring.set_password") as mock_set:
            session.save_authenticated_session(mock_mm)

        mock_set.assert_called_once_with(
            KEYRING_SERVICE, KEYRING_USERNAME, "session_token_abc"
        )
        mock_mm.save_session.assert_called_once()

    def test_save_authenticated_session_no_token(self):
        session = self._make_session(use_keyring=True)
        mock_mm = MagicMock()
        mock_mm.token = None

        with patch("keyring.set_password") as mock_set:
            session.save_authenticated_session(mock_mm)

        mock_set.assert_not_called()


class TestEnvTokenPriority:
    """Tests for MONARCH_TOKEN env var priority."""

    def test_load_token_env_var_takes_priority(self):
        session = SecureMonarchSession()

        with (
            patch.dict(os.environ, {"MONARCH_TOKEN": "env_token_value"}),
            patch("keyring.get_password") as mock_get,
        ):
            token = session.load_token()

        assert token == "env_token_value"
        mock_get.assert_not_called()

    @patch("monarch_mcp_server.secure_session.MonarchMoney")
    def test_get_authenticated_client_env_token_overrides_native_session(
        self, mock_mm_class
    ):
        """Env token should be used even when a native session exists."""
        session = SecureMonarchSession()
        mock_client = MagicMock()
        mock_mm_class.return_value = mock_client

        with patch.dict(os.environ, {"MONARCH_TOKEN": "env_priority_token"}):
            client = session.get_authenticated_client()

        assert client is mock_client
        mock_mm_class.assert_called_once_with(token="env_priority_token")

    @patch("monarch_mcp_server.secure_session.MonarchMoney")
    def test_get_authenticated_client_env_token_failure_falls_through(
        self, mock_mm_class
    ):
        """If env token construction fails, should fall through to native session."""
        with patch(
            "monarch_mcp_server.secure_session._keyring_available",
            return_value=False,
        ):
            session = SecureMonarchSession()

        native_client = MagicMock()
        native_client.token = "native_token"
        mock_mm_class.side_effect = [Exception("bad token"), native_client]

        with patch.dict(os.environ, {"MONARCH_TOKEN": "bad_env_token"}):
            client = session.get_authenticated_client()

        assert client is native_client


class TestGlobalSecureSession:
    """Tests for global secure_session instance."""

    def test_global_instance_exists(self):
        assert secure_session is not None
        assert isinstance(secure_session, SecureMonarchSession)


class TestSessionPathResolution:
    """Tests for resilient session path resolution."""

    def test_resolve_default_session_file_uses_tmp_fallback(self):
        with patch("pathlib.Path.home", side_effect=RuntimeError("no home")):
            result = _resolve_default_session_file()
            assert result == Path("/tmp/.mm/mm_session.pickle")


class TestNativeSessionLoad:
    """Tests for native session loading."""

    @patch("monarch_mcp_server.secure_session.MonarchMoney")
    def test_get_authenticated_client_native_session(self, mock_mm_class):
        """Native session with token is returned immediately."""
        with patch(
            "monarch_mcp_server.secure_session._keyring_available",
            return_value=True,
        ):
            session = SecureMonarchSession()

        mock_client = MagicMock()
        mock_client.token = "native_session_token"
        mock_mm_class.return_value = mock_client

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MONARCH_TOKEN", None)
            client = session.get_authenticated_client()

        assert client is mock_client
        mock_client.load_session.assert_called_once()
