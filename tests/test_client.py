import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from monarch_mcp_server.exceptions import AuthenticationError


@pytest.mark.asyncio
async def test_get_monarch_client_authenticated_session():
    """Test getting client when a secure session is available."""
    with patch("monarch_mcp_server.client.secure_session") as mock_session:
        # Mock authenticated client
        mock_client = MagicMock()
        mock_session.get_authenticated_client.return_value = mock_client

        from monarch_mcp_server.client import get_monarch_client

        client = await get_monarch_client()
        assert client == mock_client
        mock_session.get_authenticated_client.assert_called_once()


@pytest.mark.asyncio
async def test_get_monarch_client_env_vars():
    """Test getting client using environment variables."""
    with patch("monarch_mcp_server.client.secure_session") as mock_session:
        mock_session.get_authenticated_client.return_value = None

        with patch.dict(
            os.environ,
            {
                "MONARCH_EMAIL": "test@example.com",
                "MONARCH_PASSWORD": "password123",
                "MONARCH_MFA_SECRET": "secret",
            },
        ):
            with patch("monarch_mcp_server.client.MonarchMoney") as MockMonarchMoney:
                mock_mm_instance = MagicMock()
                mock_mm_instance.login = AsyncMock()
                MockMonarchMoney.return_value = mock_mm_instance

                from monarch_mcp_server.client import get_monarch_client

                client = await get_monarch_client()

                assert client == mock_mm_instance
                mock_mm_instance.login.assert_awaited_once_with(
                    "test@example.com", "password123", mfa_secret_key="secret"
                )
                mock_session.save_authenticated_session.assert_called_once_with(
                    mock_mm_instance
                )


@pytest.mark.asyncio
async def test_get_monarch_client_no_auth():
    """Test that AuthenticationError is raised when no credentials are found."""
    with patch("monarch_mcp_server.client.secure_session") as mock_session:
        mock_session.get_authenticated_client.return_value = None

        with patch.dict(os.environ, {}, clear=True):
            from monarch_mcp_server.client import get_monarch_client

            with pytest.raises(AuthenticationError, match="Authentication required"):
                await get_monarch_client()
