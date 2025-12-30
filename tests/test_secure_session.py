"""Tests for the secure_session module."""

import pytest
from unittest.mock import patch, MagicMock

from monarch_mcp_server.secure_session import (
    SecureMonarchSession,
    secure_session,
    KEYRING_SERVICE,
    KEYRING_USERNAME,
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
        mock_client = MagicMock()
        mock_mm_class.return_value = mock_client

        session = SecureMonarchSession()
        client = session.get_authenticated_client()

        assert client is mock_client
        mock_mm_class.assert_called_once_with(token="valid_token")

    @patch("monarch_mcp_server.secure_session.keyring")
    def test_get_authenticated_client_no_token(self, mock_keyring):
        """Test getting authenticated client when no token exists."""
        mock_keyring.get_password.return_value = None

        session = SecureMonarchSession()
        client = session.get_authenticated_client()

        assert client is None

    @patch("monarch_mcp_server.secure_session.keyring")
    @patch("monarch_mcp_server.secure_session.MonarchMoney")
    def test_get_authenticated_client_error(self, mock_mm_class, mock_keyring):
        """Test getting authenticated client when MonarchMoney raises error."""
        mock_keyring.get_password.return_value = "invalid_token"
        mock_mm_class.side_effect = Exception("Invalid token")

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
