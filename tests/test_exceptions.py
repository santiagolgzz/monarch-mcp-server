"""Tests for the exceptions module."""

from monarch_mcp_server.exceptions import (
    APIError,
    AuthenticationError,
    EmergencyStopError,
    MonarchMCPError,
    NetworkError,
    SafetyError,
    SessionExpiredError,
    ValidationError,
)


class TestMonarchMCPError:
    """Tests for base MonarchMCPError."""

    def test_basic_message(self):
        """Test basic error with message only."""
        error = MonarchMCPError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.details is None

    def test_message_with_details(self):
        """Test error with message and details."""
        error = MonarchMCPError("Operation failed", details="Connection timeout")
        assert str(error) == "Operation failed: Connection timeout"
        assert error.message == "Operation failed"
        assert error.details == "Connection timeout"


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_default_message(self):
        """Test default authentication error message."""
        error = AuthenticationError()
        assert "Authentication required" in str(error)

    def test_custom_message(self):
        """Test custom authentication error message."""
        error = AuthenticationError("Invalid credentials")
        assert str(error) == "Invalid credentials"


class TestSessionExpiredError:
    """Tests for SessionExpiredError."""

    def test_default_message(self):
        """Test default session expired message."""
        error = SessionExpiredError()
        assert "Session expired" in str(error)
        assert "login_setup.py" in str(error)

    def test_inheritance(self):
        """Test that SessionExpiredError is an AuthenticationError."""
        error = SessionExpiredError()
        assert isinstance(error, AuthenticationError)
        assert isinstance(error, MonarchMCPError)


class TestNetworkError:
    """Tests for NetworkError."""

    def test_default_message(self):
        """Test default network error message."""
        error = NetworkError()
        assert "Network error" in str(error)

    def test_with_details(self):
        """Test network error with details."""
        error = NetworkError("Connection failed", details="DNS lookup failed")
        assert "Connection failed" in str(error)
        assert "DNS lookup failed" in str(error)


class TestAPIError:
    """Tests for APIError."""

    def test_basic_api_error(self):
        """Test basic API error."""
        error = APIError("Invalid request")
        assert str(error) == "Invalid request"
        assert error.status_code is None

    def test_api_error_with_status_code(self):
        """Test API error with status code."""
        error = APIError("Not found", status_code=404)
        assert str(error) == "Not found"
        assert error.status_code == 404


class TestValidationError:
    """Tests for ValidationError."""

    def test_basic_validation_error(self):
        """Test basic validation error."""
        error = ValidationError("Invalid date format")
        assert str(error) == "Invalid date format"
        assert error.field is None

    def test_validation_error_with_field(self):
        """Test validation error with field name."""
        error = ValidationError("Invalid format", field="start_date")
        assert str(error) == "Invalid format"
        assert error.field == "start_date"


class TestSafetyError:
    """Tests for SafetyError."""

    def test_default_message(self):
        """Test default safety error message."""
        error = SafetyError()
        assert "safety" in str(error).lower()


class TestEmergencyStopError:
    """Tests for EmergencyStopError."""

    def test_emergency_stop_message(self):
        """Test emergency stop error message."""
        error = EmergencyStopError()
        assert "EMERGENCY STOP" in str(error)
        assert "disable_emergency_stop" in str(error)

    def test_inheritance(self):
        """Test that EmergencyStopError is a SafetyError."""
        error = EmergencyStopError()
        assert isinstance(error, SafetyError)
        assert isinstance(error, MonarchMCPError)
