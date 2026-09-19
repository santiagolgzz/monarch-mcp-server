"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for configuration files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_monarch_client():
    """Create a mock MonarchMoney client."""
    mock_client = MagicMock()
    mock_client.token = "test_token_xyz"

    # Set up async mock methods
    async def mock_get_accounts():
        return {
            "accounts": [
                {
                    "id": "acc_123",
                    "displayName": "Checking Account",
                    "type": {"name": "checking"},
                    "currentBalance": 1000.00,
                    "institution": {"name": "Test Bank"},
                }
            ]
        }

    async def mock_get_transactions(**kwargs):
        return {
            "allTransactions": {
                "results": [
                    {
                        "id": "txn_001",
                        "date": "2024-01-15",
                        "amount": -50.00,
                        "description": "Grocery Store",
                        "category": {"name": "Groceries"},
                        "account": {"displayName": "Checking"},
                    }
                ]
            }
        }

    async def mock_get_budgets():
        return {
            "budgets": [
                {
                    "id": "bud_001",
                    "name": "Groceries Budget",
                    "amount": 500.00,
                    "spent": 150.00,
                    "remaining": 350.00,
                    "category": {"name": "Groceries"},
                    "period": "monthly",
                }
            ]
        }

    mock_client.get_accounts = mock_get_accounts
    mock_client.get_transactions = mock_get_transactions
    mock_client.get_budgets = mock_get_budgets

    return mock_client


@pytest.fixture
def mock_keyring():
    """Mock keyring module and enable keyring in SecureMonarchSession."""
    with (
        patch(
            "monarch_mcp_server.secure_session._keyring_available", return_value=True
        ),
        patch("keyring.get_password", return_value="test_token") as mock_get,
        patch("keyring.set_password") as mock_set,
        patch("keyring.delete_password") as mock_delete,
    ):
        # Bundle into a mock namespace for test access
        mock = MagicMock()
        mock.get_password = mock_get
        mock.set_password = mock_set
        mock.delete_password = mock_delete
        yield mock


@pytest.fixture
def isolated_safety_guard(temp_config_dir):
    """Create an isolated safety guard for testing."""
    from monarch_mcp_server.safety import SafetyConfig, SafetyGuard

    config_path = str(temp_config_dir / "safety_config.json")
    config = SafetyConfig(config_path=config_path)
    guard = SafetyGuard(config=config)
    guard.operation_log_path = str(temp_config_dir / "operation_log.json")

    return guard


@pytest.fixture(autouse=True)
def writable_fastmcp_home(tmp_path, monkeypatch):
    """Force FastMCP state directory to a writable temp path for tests."""
    fastmcp_home = tmp_path / "fastmcp-home"
    fastmcp_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FASTMCP_HOME", str(fastmcp_home))

    # FastMCP settings are instantiated at import time, so patch the singleton too.
    try:
        import fastmcp

        fastmcp.settings.home = fastmcp_home
    except Exception:
        pass

    try:
        import fastmcp.server.auth.oauth_proxy as oauth_proxy

        oauth_proxy.settings.home = fastmcp_home  # type: ignore[attr-defined]
    except Exception:
        pass


@pytest.fixture(autouse=True)
def isolated_mm_home(tmp_path, monkeypatch):
    """Point ``~/.mm`` at a temp directory for every test.

    ``SafetyGuard`` resolves its log path in ``__init__`` via ``Path.home()``,
    before a fixture can override the attribute, so tests were reading and
    writing the developer's real ``~/.mm/operation_log.json``. That made daily
    counts leak between runs — a limit test could fail because an earlier run
    had already spent the budget — and appended real audit entries on every
    test invocation.
    """
    home = tmp_path / "home"
    (home / ".mm").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows equivalent

    # The global guard in safety.py is built at import time, so it resolved
    # the real home before this fixture could run. Rebuild it against the temp
    # one; this also gives each test a clean set of daily counts, which the
    # shared singleton otherwise carried between tests.
    from monarch_mcp_server import safety as safety_module

    monkeypatch.setattr(safety_module, "_safety_guard", safety_module.SafetyGuard())
    return home


@pytest.fixture(autouse=True)
def offline_pre_state():
    """Keep pre-operation snapshots from reaching the network.

    Capture runs inside ``require_safety_check``, so any test exercising a
    write path would otherwise try to authenticate against Monarch. Capture is
    best-effort and swallows the failure, but the attempt is slow and fills the
    logs with auth warnings that look like real problems.

    Tests that care about snapshot contents patch this themselves; an inner
    patch wins over this one.
    """
    client = AsyncMock()
    client.get_transaction_details.return_value = {}
    client.get_transaction_splits.return_value = {}
    client.get_accounts.return_value = {}
    client.get_transaction_categories.return_value = {}
    client.get_budgets.return_value = {}
    with patch("monarch_mcp_server.pre_state.get_monarch_client", return_value=client):
        yield client


def permit_all(guard_mock):
    """Configure a patched safety guard to allow every operation.

    Tests that exercise a write path patch ``get_safety_guard`` and then have
    to stub each gate the decorator consults. Centralizing that means adding a
    gate needs one edit here rather than one per call site — when the
    confirmation gate landed, every such test broke on an unstubbed method.

    Returns the guard mock so callers can still assert against it.
    """
    guard_mock.check_operation.return_value = (True, "OK")
    guard_mock.confirm_operation.return_value = (True, None)
    return guard_mock
