"""Tests for the GitHub identity allowlist on the OAuth MCP endpoint."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp.server.auth.auth import AccessToken

from monarch_mcp_server.auth_allowlist import (
    ALLOWED_USERS_ENV,
    AllowlistedGitHubProvider,
    get_allowed_github_users,
    parse_allowed_users,
)


def _token(login=None, sub=None) -> AccessToken:
    return AccessToken(
        token="fastmcp-jwt",
        client_id="client",
        scopes=["user"],
        expires_at=None,
        claims={"login": login, "sub": sub},
    )


def _provider(allowlist_env: str) -> AllowlistedGitHubProvider:
    """Build the provider without touching GitHubProvider's real __init__."""
    provider = AllowlistedGitHubProvider.__new__(AllowlistedGitHubProvider)
    provider._allowed_users = parse_allowed_users(allowlist_env)
    return provider


class TestParseAllowedUsers:
    def test_parses_plain_logins(self):
        allowlist = parse_allowed_users("alice,bob")
        assert allowlist.logins == frozenset({"alice", "bob"})
        assert allowlist.user_ids == frozenset()

    def test_logins_are_case_insensitive_and_strip_at_sign(self):
        allowlist = parse_allowed_users("@Alice")
        assert allowlist.permits("alice", None)
        assert allowlist.permits("ALICE", None)

    def test_parses_numeric_ids_with_prefix(self):
        allowlist = parse_allowed_users("id:12345")
        assert allowlist.user_ids == frozenset({"12345"})
        assert allowlist.logins == frozenset()

    def test_mixed_logins_and_ids(self):
        allowlist = parse_allowed_users("alice, id:999")
        assert allowlist.permits("alice", None)
        assert allowlist.permits("stranger", 999)

    def test_blank_and_trailing_entries_are_ignored(self):
        allowlist = parse_allowed_users("alice,, ,\nbob,")
        assert allowlist.logins == frozenset({"alice", "bob"})
        assert len(allowlist) == 2

    def test_empty_input_is_falsy(self):
        assert not parse_allowed_users("")
        assert not parse_allowed_users(None)
        assert not parse_allowed_users(" , , ")

    def test_bare_id_prefix_does_not_create_empty_identity(self):
        """`id:` with nothing after it must not authorize a blank subject."""
        allowlist = parse_allowed_users("id:")
        assert not allowlist
        assert not allowlist.permits("", "")


class TestPermits:
    def test_rejects_unknown_login(self):
        assert not parse_allowed_users("alice").permits("mallory", None)

    def test_login_entry_does_not_match_a_numeric_id(self):
        """A login of '123' must not authorize the account whose id is 123."""
        allowlist = parse_allowed_users("123")
        assert allowlist.permits("123", None)
        assert not allowlist.permits("mallory", 123)

    def test_id_entry_does_not_match_a_login(self):
        allowlist = parse_allowed_users("id:123")
        assert not allowlist.permits("123", None)
        assert allowlist.permits("anyone", 123)

    def test_missing_claims_are_rejected(self):
        allowlist = parse_allowed_users("alice")
        assert not allowlist.permits(None, None)

    def test_non_string_login_is_rejected(self):
        allowlist = parse_allowed_users("alice")
        assert not allowlist.permits({"login": "alice"}, None)


class TestGetAllowedGithubUsers:
    def test_reads_from_environment(self):
        with patch.dict(os.environ, {ALLOWED_USERS_ENV: "alice"}, clear=True):
            assert get_allowed_github_users().permits("alice", None)

    def test_raises_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match=ALLOWED_USERS_ENV):
                get_allowed_github_users()

    def test_raises_when_blank(self):
        with patch.dict(os.environ, {ALLOWED_USERS_ENV: "  , "}, clear=True):
            with pytest.raises(ValueError, match="any GitHub account"):
                get_allowed_github_users()


class TestProviderVerifyToken:
    async def test_allows_listed_login(self):
        provider = _provider("alice")
        granted = _token(login="alice", sub="1")
        with patch(
            "monarch_mcp_server.auth_allowlist.GitHubProvider.verify_token",
            new=AsyncMock(return_value=granted),
        ):
            assert await provider.verify_token("jwt") is granted

    async def test_rejects_unlisted_login(self):
        provider = _provider("alice")
        with patch(
            "monarch_mcp_server.auth_allowlist.GitHubProvider.verify_token",
            new=AsyncMock(return_value=_token(login="mallory", sub="2")),
        ):
            assert await provider.verify_token("jwt") is None

    async def test_allows_listed_user_id_after_rename(self):
        """An id: entry keeps working when the account's login changes."""
        provider = _provider("id:42")
        with patch(
            "monarch_mcp_server.auth_allowlist.GitHubProvider.verify_token",
            new=AsyncMock(return_value=_token(login="new-name", sub="42")),
        ):
            assert await provider.verify_token("jwt") is not None

    async def test_passes_through_upstream_rejection(self):
        provider = _provider("alice")
        with patch(
            "monarch_mcp_server.auth_allowlist.GitHubProvider.verify_token",
            new=AsyncMock(return_value=None),
        ):
            assert await provider.verify_token("jwt") is None

    async def test_rejects_token_with_no_identity_claims(self):
        provider = _provider("alice")
        with patch(
            "monarch_mcp_server.auth_allowlist.GitHubProvider.verify_token",
            new=AsyncMock(return_value=_token()),
        ):
            assert await provider.verify_token("jwt") is None

    async def test_logs_rejected_identity(self, caplog):
        provider = _provider("alice")
        with patch(
            "monarch_mcp_server.auth_allowlist.GitHubProvider.verify_token",
            new=AsyncMock(return_value=_token(login="mallory", sub="2")),
        ):
            await provider.verify_token("jwt")
        assert "mallory" in caplog.text

    def test_constructor_refuses_empty_allowlist(self):
        with pytest.raises(ValueError, match="empty allowlist"):
            AllowlistedGitHubProvider(
                allowed_users=parse_allowed_users(""),
                client_id="id",
                client_secret="secret",
                base_url="http://localhost:8000",
            )


class TestServerStartup:
    """The OAuth endpoint must not come up without an allowlist."""

    def _oauth_env(self, **overrides):
        env = {
            "MCP_AUTH_MODE": "oauth",
            "GITHUB_CLIENT_ID": "test_client_id",
            "GITHUB_CLIENT_SECRET": "test_client_secret",
            "BASE_URL": "http://localhost:8000",
            ALLOWED_USERS_ENV: "alice",
        }
        env.update(overrides)
        return env

    def test_oauth_mode_requires_allowlist(self):
        from monarch_mcp_server.http_server import create_mcp_server

        env = self._oauth_env()
        env.pop(ALLOWED_USERS_ENV)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match=ALLOWED_USERS_ENV):
                create_mcp_server()

    def test_both_mode_requires_allowlist(self):
        from monarch_mcp_server.http_server import create_mcp_server

        env = self._oauth_env(MCP_AUTH_MODE="both", MCP_AUTH_TOKEN="tok")
        env.pop(ALLOWED_USERS_ENV)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match=ALLOWED_USERS_ENV):
                create_mcp_server()

    def test_token_only_mode_does_not_require_allowlist(self):
        """Token mode has no OAuth surface, so the allowlist is not needed."""
        from monarch_mcp_server.http_server import create_mcp_server

        env = {
            "MCP_AUTH_MODE": "token",
            "MCP_AUTH_TOKEN": "test-token",
            "BASE_URL": "http://localhost:8000",
        }
        with patch.dict(os.environ, env, clear=True):
            assert create_mcp_server() is not None

    def test_oauth_mode_starts_with_allowlist(self):
        from monarch_mcp_server.http_server import create_mcp_server

        with patch.dict(os.environ, self._oauth_env(), clear=True):
            server = create_mcp_server()
        assert isinstance(server.auth, AllowlistedGitHubProvider)
