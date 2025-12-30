"""Tests for the utils module."""

import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

from monarch_mcp_server.utils import (
    get_config_dir,
    get_config_path,
    format_result,
    format_error,
    validate_date_format,
    validate_positive_amount,
    validate_non_empty_string,
    classify_exception,
)
from monarch_mcp_server.exceptions import (
    MonarchMCPError,
    AuthenticationError,
    NetworkError,
    APIError,
    ValidationError,
    SessionExpiredError,
)


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_returns_path_object(self):
        """Test that get_config_dir returns a Path object."""
        result = get_config_dir()
        assert isinstance(result, Path)

    def test_returns_mm_directory(self):
        """Test that the directory ends with .mm."""
        result = get_config_dir()
        assert result.name == ".mm"

    def test_parent_is_home(self):
        """Test that parent directory is user home."""
        result = get_config_dir()
        assert result.parent == Path.home()


class TestGetConfigPath:
    """Tests for get_config_path function."""

    def test_returns_correct_path(self):
        """Test that get_config_path returns correct file path."""
        result = get_config_path("test_file.json")
        expected = Path.home() / ".mm" / "test_file.json"
        assert result == expected


class TestFormatResult:
    """Tests for format_result function."""

    def test_format_dict(self):
        """Test formatting a dictionary."""
        data = {"key": "value", "number": 42}
        result = format_result(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_format_list(self):
        """Test formatting a list."""
        data = [1, 2, 3, "test"]
        result = format_result(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_format_with_special_types(self):
        """Test formatting with types that need special handling."""
        from datetime import datetime, date
        
        data = {
            "date": date(2024, 1, 15),
            "datetime": datetime(2024, 1, 15, 10, 30),
        }
        result = format_result(data)
        # Should not raise an exception
        parsed = json.loads(result)
        assert "2024-01-15" in parsed["date"]


class TestFormatError:
    """Tests for format_error function."""

    def test_format_monarch_error(self):
        """Test formatting a MonarchMCPError."""
        error = AuthenticationError("Invalid token", details="Token expired")
        result = format_error(error, "get_accounts")
        assert "get_accounts" in result
        assert "Invalid token" in result

    def test_format_generic_exception(self):
        """Test formatting a generic exception."""
        error = ValueError("Something went wrong")
        result = format_error(error, "update_account")
        assert "update_account" in result


class TestValidateDateFormat:
    """Tests for validate_date_format function."""

    def test_valid_date(self):
        """Test valid date format."""
        result = validate_date_format("2024-01-15")
        assert result == "2024-01-15"

    def test_none_value(self):
        """Test None value returns None."""
        result = validate_date_format(None)
        assert result is None

    def test_invalid_format_raises(self):
        """Test invalid format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_date_format("01-15-2024")
        assert "Invalid date format" in str(exc_info.value)

    def test_invalid_format_wrong_separators(self):
        """Test invalid format with wrong separators."""
        with pytest.raises(ValidationError):
            validate_date_format("2024/01/15")

    def test_custom_field_name_in_error(self):
        """Test custom field name appears in error."""
        with pytest.raises(ValidationError) as exc_info:
            validate_date_format("bad-date", field_name="start_date")
        assert "start_date" in str(exc_info.value)


class TestValidatePositiveAmount:
    """Tests for validate_positive_amount function."""

    def test_positive_amount(self):
        """Test positive amount passes validation."""
        result = validate_positive_amount(100.50)
        assert result == 100.50

    def test_zero_raises(self):
        """Test zero raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_positive_amount(0)

    def test_negative_raises(self):
        """Test negative amount raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_positive_amount(-50.00)


class TestValidateNonEmptyString:
    """Tests for validate_non_empty_string function."""

    def test_valid_string(self):
        """Test valid non-empty string."""
        result = validate_non_empty_string("test value", "field")
        assert result == "test value"

    def test_strips_whitespace(self):
        """Test that whitespace is stripped."""
        result = validate_non_empty_string("  test  ", "field")
        assert result == "test"

    def test_empty_string_raises(self):
        """Test empty string raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_non_empty_string("", "field_name")

    def test_whitespace_only_raises(self):
        """Test whitespace-only string raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_non_empty_string("   ", "field_name")

    def test_none_raises(self):
        """Test None raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_non_empty_string(None, "field_name")


class TestClassifyException:
    """Tests for classify_exception function."""

    def test_classify_auth_error(self):
        """Test classification of authentication errors."""
        error = Exception("Authentication failed: invalid token")
        result = classify_exception(error)
        assert isinstance(result, AuthenticationError)

    def test_classify_expired_session(self):
        """Test classification of expired session."""
        error = Exception("Session has expired, please login again")
        result = classify_exception(error)
        assert isinstance(result, SessionExpiredError)

    def test_classify_network_error(self):
        """Test classification of network errors."""
        error = Exception("Connection timeout after 30s")
        result = classify_exception(error)
        assert isinstance(result, NetworkError)

    def test_classify_api_error(self):
        """Test classification of API errors."""
        error = Exception("API returned 404 not found")
        result = classify_exception(error)
        assert isinstance(result, APIError)

    def test_classify_validation_error(self):
        """Test classification of validation errors."""
        error = Exception("Validation failed: missing required field")
        result = classify_exception(error)
        assert isinstance(result, ValidationError)

    def test_classify_generic_error(self):
        """Test classification falls back to MonarchMCPError."""
        error = Exception("Something completely unknown happened")
        result = classify_exception(error)
        assert isinstance(result, MonarchMCPError)
