"""GitHub identity allowlist for the OAuth-protected MCP endpoint.

Completing the GitHub OAuth flow proves only that the caller holds *some*
GitHub account. It says nothing about which accounts should be able to reach
this server, and this server exposes one household's financial data with write
access. This module supplies that second check: an explicit list of GitHub
identities, enforced on every authenticated request.

Identities are configured through ``MCP_ALLOWED_GITHUB_USERS`` as a
comma-separated list. Two forms are accepted:

- A login, optionally ``@``-prefixed: ``santiagolgzz`` or ``@santiagolgzz``.
- A numeric user ID, ``id:``-prefixed: ``id:246566418``.

Prefer the ID form when it matters. GitHub logins can be changed, and a
released login can be registered by someone else, so a login-based entry can in
principle be inherited by a different person. A user ID is permanent.

There is no implicit "allow everyone" state: when OAuth is enabled and no
allowlist is configured, startup fails rather than serving an endpoint that
accepts any GitHub account.
"""

import logging
import os
from collections.abc import Iterable

from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.providers.github import GitHubProvider

logger = logging.getLogger(__name__)

ALLOWED_USERS_ENV = "MCP_ALLOWED_GITHUB_USERS"

_ID_PREFIX = "id:"


class GitHubUserAllowlist:
    """An immutable set of permitted GitHub logins and user IDs."""

    def __init__(self, logins: Iterable[str], user_ids: Iterable[str]) -> None:
        self.logins = frozenset(logins)
        self.user_ids = frozenset(user_ids)

    def __bool__(self) -> bool:
        return bool(self.logins or self.user_ids)

    def __len__(self) -> int:
        return len(self.logins) + len(self.user_ids)

    def permits(self, login: object, user_id: object) -> bool:
        """Return True when either identity claim matches an allowlist entry."""
        if isinstance(login, str) and login.strip().casefold() in self.logins:
            return True
        # GitHub user IDs arrive as the `sub` claim, typed as str or int
        # depending on the code path that produced the token.
        if isinstance(user_id, str | int):
            return str(user_id).strip() in self.user_ids
        return False


def parse_allowed_users(raw: str | None) -> GitHubUserAllowlist:
    """Parse the allowlist env var into logins and user IDs.

    Blank entries are ignored so that trailing commas and wrapped lines in
    deployment config do not silently create an empty-string identity.
    """
    logins: set[str] = set()
    user_ids: set[str] = set()

    for chunk in (raw or "").replace("\n", ",").split(","):
        entry = chunk.strip()
        if not entry:
            continue
        if entry.casefold().startswith(_ID_PREFIX):
            user_id = entry[len(_ID_PREFIX) :].strip()
            if user_id:
                user_ids.add(user_id)
            continue
        logins.add(entry.lstrip("@").strip().casefold())

    return GitHubUserAllowlist(logins, user_ids)


def get_allowed_github_users() -> GitHubUserAllowlist:
    """Read and validate the allowlist, failing closed when it is unset."""
    allowlist = parse_allowed_users(os.getenv(ALLOWED_USERS_ENV))
    if not allowlist:
        raise ValueError(
            f"{ALLOWED_USERS_ENV} is required when MCP_AUTH_MODE=oauth or "
            "MCP_AUTH_MODE=both. Set it to a comma-separated list of the "
            "GitHub logins (or id:<numeric id> entries) permitted to use this "
            "server. Without it, any GitHub account could authenticate."
        )
    return allowlist


class AllowlistedGitHubProvider(GitHubProvider):
    """GitHubProvider that additionally checks *who* authenticated.

    The check runs in ``verify_token``, which every authenticated request
    passes through, rather than only at login. Removing someone from the
    allowlist therefore takes effect on their next request instead of
    whenever their existing token happens to expire.
    """

    def __init__(self, *, allowed_users: GitHubUserAllowlist, **kwargs) -> None:
        if not allowed_users:
            raise ValueError(
                "AllowlistedGitHubProvider requires at least one allowed GitHub "
                "identity; refusing to start with an empty allowlist."
            )
        super().__init__(**kwargs)
        self._allowed_users = allowed_users

    async def verify_token(self, token: str) -> AccessToken | None:
        access_token = await super().verify_token(token)
        if access_token is None:
            return None

        claims = access_token.claims or {}
        login = claims.get("login")
        user_id = claims.get("sub")

        if not self._allowed_users.permits(login, user_id):
            # Log the rejected identity so the operator can tell an
            # authorized user who mistyped from an outsider probing the URL.
            logger.warning(
                "Rejected authenticated GitHub identity not in allowlist: "
                "login=%r id=%r",
                login,
                user_id,
            )
            return None

        return access_token
