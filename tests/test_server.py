"""Tests for the server module MCP tools."""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock


class TestToolInputValidation:
    """Tests for input validation on MCP tools."""

    def test_get_transactions_validates_date_format(self):
        """Test that get_transactions validates date format."""
        from monarch_mcp_server.server import get_transactions
        
        # Invalid date format should return validation error
        result = get_transactions(start_date="01-15-2024")
        assert "Validation error" in result or "Invalid date format" in result
        
    def test_get_transactions_accepts_valid_dates(self):
        """Test that get_transactions accepts valid date format."""
        from monarch_mcp_server.server import get_transactions
        
        # This should attempt to make API call (will fail without auth)
        # but should NOT fail on validation
        result = get_transactions(start_date="2024-01-15", end_date="2024-01-31")
        assert "Invalid date format" not in result

    def test_create_transaction_validates_account_id(self):
        """Test that create_transaction validates account_id."""
        from monarch_mcp_server.server import create_transaction

        # Empty account_id should fail validation
        result = create_transaction(
            account_id="",
            amount=50.0,
            merchant_name="Test Merchant",
            category_id="cat_123",
            date="2024-01-15"
        )
        assert "Validation error" in result or "account_id" in result

    def test_create_transaction_validates_merchant_name(self):
        """Test that create_transaction validates merchant_name."""
        from monarch_mcp_server.server import create_transaction

        # Empty merchant_name should fail validation
        result = create_transaction(
            account_id="acc_123",
            amount=50.0,
            merchant_name="   ",  # Whitespace only
            category_id="cat_123",
            date="2024-01-15"
        )
        assert "Validation error" in result or "merchant_name" in result

    def test_create_transaction_validates_date(self):
        """Test that create_transaction validates date format."""
        from monarch_mcp_server.server import create_transaction

        # Invalid date format should fail validation
        result = create_transaction(
            account_id="acc_123",
            amount=50.0,
            merchant_name="Test Merchant",
            category_id="cat_123",
            date="January 15, 2024"  # Wrong format
        )
        assert "Validation error" in result or "Invalid date format" in result

    def test_update_transaction_validates_transaction_id(self):
        """Test that update_transaction validates transaction_id."""
        from monarch_mcp_server.server import update_transaction

        # Empty transaction_id should fail validation
        result = update_transaction(
            transaction_id="",
            amount=100.0
        )
        assert "transaction_id" in result
        assert "cannot be empty" in result or "Validation error" in result

    def test_update_transaction_validates_date_if_provided(self):
        """Test that update_transaction validates date format when provided."""
        from monarch_mcp_server.server import update_transaction
        
        # Invalid date format should fail validation
        result = update_transaction(
            transaction_id="txn_123",
            date="bad-date-format"
        )
        assert "Validation error" in result or "Invalid date format" in result

    def test_create_manual_account_validates_name(self):
        """Test that create_manual_account validates account_name."""
        from monarch_mcp_server.server import create_manual_account
        
        # Empty account_name should fail validation
        result = create_manual_account(
            account_name="",
            account_type="checking",
            current_balance=1000.0
        )
        assert "Validation error" in result
        assert "account_name" in result

    def test_create_manual_account_validates_type(self):
        """Test that create_manual_account validates account_type."""
        from monarch_mcp_server.server import create_manual_account
        
        # Empty account_type should fail validation
        result = create_manual_account(
            account_name="My Account",
            account_type="   ",  # Whitespace only
            current_balance=1000.0
        )
        assert "Validation error" in result
        assert "account_type" in result

    def test_create_tag_validates_name(self):
        """Test that create_tag validates name."""
        from monarch_mcp_server.server import create_tag
        
        # Empty name should fail validation
        result = create_tag(name="")
        assert "Validation error" in result
        assert "name" in result


class TestAuthenticationTools:
    """Tests for authentication-related tools."""

    def test_setup_authentication_returns_instructions(self):
        """Test that setup_authentication returns setup instructions."""
        from monarch_mcp_server.server import setup_authentication
        
        result = setup_authentication()
        
        assert "login_setup.py" in result
        assert "email" in result.lower() or "Email" in result
        assert "2FA" in result or "MFA" in result

    def test_check_auth_status_handles_no_token(self):
        """Test that check_auth_status handles missing token gracefully."""
        from monarch_mcp_server.server import check_auth_status
        
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.load_token.return_value = None
            
            result = check_auth_status()
            
            assert "No authentication token" in result or "token" in result.lower()


class TestSafetyTools:
    """Tests for safety management tools."""

    def test_get_safety_stats_returns_json(self):
        """Test that get_safety_stats returns valid JSON."""
        from monarch_mcp_server.server import get_safety_stats
        
        result = get_safety_stats()
        
        # Should be valid JSON
        try:
            data = json.loads(result)
            assert isinstance(data, dict)
        except json.JSONDecodeError:
            # If not JSON, should be an error message
            assert "Error" in result

    def test_enable_emergency_stop_returns_status(self):
        """Test that enable_emergency_stop returns appropriate status."""
        from monarch_mcp_server.server import enable_emergency_stop
        
        result = enable_emergency_stop()
        
        # Should indicate emergency stop is enabled
        assert "emergency" in result.lower() or "EMERGENCY" in result

    def test_disable_emergency_stop_returns_status(self):
        """Test that disable_emergency_stop returns appropriate status."""
        from monarch_mcp_server.server import disable_emergency_stop
        
        result = disable_emergency_stop()
        
        # Should indicate emergency stop is disabled
        assert "emergency" in result.lower() or "disabled" in result.lower() or "re-enable" in result.lower()


class TestToolWithMockedClient:
    """Tests for MCP tools with mocked MonarchMoney client."""

    @pytest.fixture
    def mock_authenticated_client(self):
        """Create a mock authenticated MonarchMoney client."""
        mock_client = MagicMock()
        mock_client.token = "test_token_xyz"
        
        # Mock async methods
        mock_client.get_accounts = AsyncMock(return_value={
            "accounts": [
                {
                    "id": "acc_123",
                    "displayName": "Test Checking",
                    "type": {"name": "checking"},
                    "currentBalance": 1500.00,
                    "institution": {"name": "Test Bank"},
                    "isActive": True,
                }
            ]
        })
        
        mock_client.get_transactions = AsyncMock(return_value={
            "allTransactions": {
                "results": [
                    {
                        "id": "txn_001",
                        "date": "2024-01-15",
                        "amount": -50.00,
                        "description": "Test Transaction",
                        "category": {"name": "Groceries"},
                        "account": {"displayName": "Checking"},
                        "merchant": {"name": "Store"},
                        "isPending": False,
                    }
                ]
            }
        })
        
        mock_client.get_budgets = AsyncMock(return_value={
            "budgets": [
                {
                    "id": "bud_001",
                    "name": "Groceries",
                    "amount": 500.00,
                    "spent": 200.00,
                    "remaining": 300.00,
                    "category": {"name": "Groceries"},
                    "period": "monthly",
                }
            ]
        })
        
        mock_client.get_cashflow = AsyncMock(return_value={
            "income": 5000.00,
            "expenses": 3500.00,
            "net": 1500.00,
        })
        
        return mock_client

    def test_get_accounts_formats_response(self, mock_authenticated_client):
        """Test that get_accounts properly formats the response."""
        from monarch_mcp_server.server import get_accounts
        
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.get_authenticated_client.return_value = mock_authenticated_client
            
            result = get_accounts()
            
            # Should be valid JSON array
            data = json.loads(result)
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["id"] == "acc_123"
            assert data[0]["name"] == "Test Checking"
            assert data[0]["balance"] == 1500.00

    def test_get_transactions_formats_response(self, mock_authenticated_client):
        """Test that get_transactions properly formats the response."""
        from monarch_mcp_server.server import get_transactions
        
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.get_authenticated_client.return_value = mock_authenticated_client
            
            result = get_transactions(limit=10)
            
            # Should be valid JSON array
            data = json.loads(result)
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["id"] == "txn_001"
            assert data[0]["amount"] == -50.00

    def test_get_budgets_formats_response(self, mock_authenticated_client):
        """Test that get_budgets properly formats the response."""
        from monarch_mcp_server.server import get_budgets
        
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.get_authenticated_client.return_value = mock_authenticated_client
            
            result = get_budgets()
            
            # Should be valid JSON array
            data = json.loads(result)
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["id"] == "bud_001"
            assert data[0]["spent"] == 200.00

    def test_get_cashflow_returns_data(self, mock_authenticated_client):
        """Test that get_cashflow returns cashflow data."""
        from monarch_mcp_server.server import get_cashflow
        
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.get_authenticated_client.return_value = mock_authenticated_client
            
            result = get_cashflow()
            
            # Should be valid JSON
            data = json.loads(result)
            assert "income" in data or isinstance(data, dict)


class TestClientAuthentication:
    """Tests for client authentication flow."""

    def test_get_monarch_client_uses_keyring_token(self):
        """Test that get_monarch_client uses token from keyring."""
        from monarch_mcp_server.server import get_monarch_client
        from monarch_mcp_server.utils import run_async
        
        mock_client = MagicMock()
        
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.get_authenticated_client.return_value = mock_client
            
            result = run_async(get_monarch_client())
            
            assert result == mock_client
            mock_session.get_authenticated_client.assert_called_once()

    def test_get_monarch_client_raises_without_auth(self):
        """Test that get_monarch_client raises error without authentication."""
        from monarch_mcp_server.server import get_monarch_client
        from monarch_mcp_server.utils import run_async
        import os
        
        with patch("monarch_mcp_server.server.secure_session") as mock_session:
            mock_session.get_authenticated_client.return_value = None
            
            # Also mock environment to have no credentials
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(RuntimeError) as exc_info:
                    run_async(get_monarch_client())
                
                assert "Authentication needed" in str(exc_info.value)
