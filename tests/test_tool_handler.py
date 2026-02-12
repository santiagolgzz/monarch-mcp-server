"""Tests for tool_handler decorator, specifically auth retry logic."""

from unittest.mock import patch

import pytest

from monarch_mcp_server.exceptions import AuthenticationError, SessionExpiredError
from monarch_mcp_server.tools._common import _is_auth_error, tool_handler


class TestIsAuthError:
    def test_authentication_error(self):
        assert _is_auth_error(AuthenticationError()) is True

    def test_session_expired_error(self):
        assert _is_auth_error(SessionExpiredError()) is True

    def test_401_in_message(self):
        assert _is_auth_error(Exception("HTTP 401 Unauthorized")) is True

    def test_unauthorized_in_message(self):
        assert _is_auth_error(Exception("Request unauthorized")) is True

    def test_generic_error(self):
        assert _is_auth_error(ValueError("bad input")) is False

    def test_network_error(self):
        assert _is_auth_error(ConnectionError("timeout")) is False


class TestToolHandlerRetry:
    @pytest.mark.anyio
    async def test_retries_on_auth_error_and_succeeds(self):
        """If the first call fails with auth error but retry succeeds, return the result."""
        call_count = 0

        @tool_handler("test_op")
        async def my_tool() -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise AuthenticationError("session expired")
            return {"ok": True}

        with patch("monarch_mcp_server.tools._common.secure_session") as mock_session:
            result = await my_tool()

        assert result == {"ok": True}
        assert call_count == 2
        mock_session.delete_token.assert_called_once()

    @pytest.mark.anyio
    async def test_retries_on_401_string_and_succeeds(self):
        """Auth retry also triggers on '401' in the error message."""
        call_count = 0

        @tool_handler("test_op")
        async def my_tool() -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("HTTP 401 Unauthorized")
            return {"ok": True}

        with patch("monarch_mcp_server.tools._common.secure_session") as mock_session:
            result = await my_tool()

        assert result == {"ok": True}
        assert call_count == 2
        mock_session.delete_token.assert_called_once()

    @pytest.mark.anyio
    async def test_raises_after_retry_fails(self):
        """If retry also fails, raise the retry error (not the original)."""

        @tool_handler("test_op")
        async def my_tool() -> dict:
            raise AuthenticationError("still broken")

        with patch("monarch_mcp_server.tools._common.secure_session"):
            with pytest.raises(RuntimeError, match="still broken"):
                await my_tool()

    @pytest.mark.anyio
    async def test_no_retry_on_non_auth_error(self):
        """Non-auth errors should NOT trigger a retry."""
        call_count = 0

        @tool_handler("test_op")
        async def my_tool() -> dict:
            nonlocal call_count
            call_count += 1
            raise ValueError("bad input")

        with patch("monarch_mcp_server.tools._common.secure_session") as mock_session:
            with pytest.raises(RuntimeError, match="bad input"):
                await my_tool()

        assert call_count == 1
        mock_session.delete_token.assert_not_called()

    @pytest.mark.anyio
    async def test_retries_at_most_once(self):
        """Auth retry happens exactly once, not infinitely."""
        call_count = 0

        @tool_handler("test_op")
        async def my_tool() -> dict:
            nonlocal call_count
            call_count += 1
            raise AuthenticationError("always fails")

        with patch("monarch_mcp_server.tools._common.secure_session"):
            with pytest.raises(RuntimeError):
                await my_tool()

        assert call_count == 2  # original + 1 retry

    @pytest.mark.anyio
    async def test_passes_args_on_retry(self):
        """Tool arguments are preserved across the retry."""
        call_count = 0
        received_args = []

        @tool_handler("test_op")
        async def my_tool(account_id: str, limit: int = 10) -> dict:
            nonlocal call_count
            call_count += 1
            received_args.append((account_id, limit))
            if call_count == 1:
                raise AuthenticationError("expired")
            return {"account_id": account_id, "limit": limit}

        with patch("monarch_mcp_server.tools._common.secure_session"):
            result = await my_tool("acc_123", limit=50)

        assert result == {"account_id": "acc_123", "limit": 50}
        assert received_args == [("acc_123", 50), ("acc_123", 50)]

    @pytest.mark.anyio
    async def test_success_on_first_try_no_retry(self):
        """Happy path: no errors, no retry, no delete_token."""
        call_count = 0

        @tool_handler("test_op")
        async def my_tool() -> dict:
            nonlocal call_count
            call_count += 1
            return {"ok": True}

        with patch("monarch_mcp_server.tools._common.secure_session") as mock_session:
            result = await my_tool()

        assert result == {"ok": True}
        assert call_count == 1
        mock_session.delete_token.assert_not_called()
