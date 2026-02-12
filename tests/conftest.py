"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    """Mock keyring module."""
    with patch("monarch_mcp_server.secure_session.keyring") as mock:
        mock.get_password.return_value = "test_token"
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
