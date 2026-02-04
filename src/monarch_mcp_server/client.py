"""
Unified authentication and client management for Monarch Money.
"""

import logging
import os

from monarchmoney import MonarchMoney

from monarch_mcp_server.exceptions import AuthenticationError
from monarch_mcp_server.secure_session import secure_session

logger = logging.getLogger(__name__)


async def get_monarch_client() -> MonarchMoney:
    """
    Get an authenticated MonarchMoney client instance.

    Priority:
    1. MONARCH_TOKEN environment variable (direct token auth)
    2. Existing secure session (keyring/file with cookies)
    3. Environment variables (MONARCH_EMAIL, MONARCH_PASSWORD, MONARCH_MFA_SECRET)

    Returns:
        MonarchMoney: Authenticated client

    Raises:
        AuthenticationError: If authentication fails or no credentials found
    """
    # 1. Try to load from secure session
    try:
        client = secure_session.get_authenticated_client()
        if client is not None:
            logger.debug("Using existing authenticated session")
            return client
    except Exception as e:
        logger.error(
            f"Failed to load secure session: {e}. "
            "Run 'python login_setup.py' to re-authenticate, "
            "or set MONARCH_EMAIL and MONARCH_PASSWORD environment variables."
        )

    # 2. Try environment variables
    email = os.getenv("MONARCH_EMAIL")
    password = os.getenv("MONARCH_PASSWORD")

    if email and password:
        logger.info("Attempting login with environment variables")
        try:
            client = MonarchMoney()
            mfa_secret = os.getenv("MONARCH_MFA_SECRET")

            # Login (this handles MFA if secret provided)
            await client.login(email, password, mfa_secret_key=mfa_secret)

            # Save the new session
            secure_session.save_authenticated_session(client)
            return client
        except Exception as e:
            logger.error(f"Login with environment variables failed: {e}")
            raise AuthenticationError(f"Login failed: {str(e)}") from e

    # 3. No credentials found
    raise AuthenticationError(
        "Authentication required! Please run 'python login_setup.py' to authenticate interactively, "
        "or set MONARCH_EMAIL and MONARCH_PASSWORD environment variables."
    )
