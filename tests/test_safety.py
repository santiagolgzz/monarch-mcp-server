"""Tests for the safety module."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from monarch_mcp_server.safety import (
    SafetyConfig,
    SafetyGuard,
    get_safety_guard,
    require_safety_check,
)


class TestSafetyConfig:
    """Tests for SafetyConfig class."""

    def test_default_config_values(self):
        """Test default configuration values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            config = SafetyConfig(config_path=config_path)

            assert "delete_transaction" in config.config["require_approval"]
            assert "delete_account" in config.config["require_approval"]
            assert config.config["emergency_stop"] is False
            assert config.config["enabled"] is True

    def test_requires_approval_true(self):
        """Test requires_approval returns true for destructive ops."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            config = SafetyConfig(config_path=config_path)

            assert config.requires_approval("delete_transaction") is True
            assert config.requires_approval("delete_account") is True

    def test_requires_approval_false(self):
        """Test requires_approval returns false for non-destructive ops."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            config = SafetyConfig(config_path=config_path)

            assert config.requires_approval("get_accounts") is False
            assert config.requires_approval("get_transactions") is False

    def test_should_warn(self):
        """Test should_warn for write operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            config = SafetyConfig(config_path=config_path)

            assert config.should_warn("create_transaction") is True
            assert config.should_warn("update_transaction") is True
            assert config.should_warn("get_accounts") is False

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            config = SafetyConfig(config_path=config_path)

            # Modify and save
            config.config["emergency_stop"] = True
            config.save_config()

            # Load again
            config2 = SafetyConfig(config_path=config_path)
            assert config2.config["emergency_stop"] is True


class TestSafetyGuard:
    """Tests for SafetyGuard class."""

    @pytest.fixture
    def temp_guard(self):
        """Create a SafetyGuard with temporary files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "safety_config.json")
            config = SafetyConfig(config_path=config_path)
            guard = SafetyGuard(config=config)
            guard.operation_log_path = str(Path(tmpdir) / "operation_log.json")
            yield guard

    def test_check_operation_allowed(self, temp_guard):
        """Test check_operation allows normal operations."""
        allowed, message = temp_guard.check_operation("get_accounts")
        assert allowed is True

    def test_check_operation_emergency_stop(self, temp_guard):
        """Test check_operation blocks when emergency stop is active."""
        temp_guard.config.config["emergency_stop"] = True
        allowed, message = temp_guard.check_operation("create_transaction")
        assert allowed is False
        assert "EMERGENCY STOP" in message

    def test_check_operation_disabled_safety(self, temp_guard):
        """Test check_operation allows when safety is disabled."""
        temp_guard.config.config["enabled"] = False
        allowed, message = temp_guard.check_operation("delete_account")
        assert allowed is True

    def test_record_operation(self, temp_guard):
        """Test recording an operation."""
        # Reset counts to ensure clean state for this test
        from collections import defaultdict

        temp_guard.daily_counts = defaultdict(lambda: defaultdict(int))

        temp_guard.record_operation(
            "create_transaction",
            success=True,
            operation_details={"account_id": "123", "amount": 50.00},
        )

        today = datetime.now().strftime("%Y-%m-%d")
        assert temp_guard.daily_counts[today]["create_transaction"] == 1

    def test_get_operation_stats(self, temp_guard):
        """Test getting operation statistics."""
        # Reset counts to ensure clean state for this test
        from collections import defaultdict

        temp_guard.daily_counts = defaultdict(lambda: defaultdict(int))

        temp_guard.record_operation("create_transaction", success=True)
        temp_guard.record_operation("create_transaction", success=True)
        temp_guard.record_operation("update_transaction", success=True)

        stats = temp_guard.get_operation_stats()

        assert stats["total_operations_today"] == 3
        assert stats["operations_today"]["create_transaction"] == 2
        assert stats["operations_today"]["update_transaction"] == 1
        assert "emergency_stop" in stats

    def test_enable_emergency_stop(self, temp_guard):
        """Test enabling emergency stop."""
        result = temp_guard.enable_emergency_stop()
        assert "activated" in result.lower()
        assert temp_guard.config.config["emergency_stop"] is True

    def test_disable_emergency_stop(self, temp_guard):
        """Test disabling emergency stop."""
        temp_guard.config.config["emergency_stop"] = True
        result = temp_guard.disable_emergency_stop()
        assert "deactivated" in result.lower()
        assert temp_guard.config.config["emergency_stop"] is False


class TestRequireSafetyCheckDecorator:
    """Tests for require_safety_check decorator."""

    @pytest.mark.asyncio
    async def test_decorator_allows_operation(self):
        """Test decorator allows operation when safety checks pass."""

        @require_safety_check("test_operation")
        async def test_func(value):
            return f"Result: {value}"

        # Temporarily disable safety for test
        guard = get_safety_guard()
        original_enabled = guard.config.config.get("enabled", True)
        guard.config.config["enabled"] = False

        try:
            result = await test_func("test")
            assert result == "Result: test"
        finally:
            guard.config.config["enabled"] = original_enabled

    @pytest.mark.asyncio
    async def test_decorator_blocks_on_emergency_stop(self):
        """Test decorator blocks operation during emergency stop."""

        @require_safety_check("test_operation")
        async def test_func():
            return "Should not execute"

        guard = get_safety_guard()
        original_stop = guard.config.config.get("emergency_stop", False)
        guard.config.config["emergency_stop"] = True

        try:
            result = await test_func()
            result_data = json.loads(result)

            assert "error" in result_data
            assert "blocked" in result_data["error"]
            assert "EMERGENCY STOP" in result_data["reason"]
        finally:
            guard.config.config["emergency_stop"] = original_stop


class TestGenerateRollbackInfo:
    """Tests for rollback info generation."""

    @pytest.fixture
    def temp_guard(self):
        """Create a SafetyGuard with temporary files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "safety_config.json")
            config = SafetyConfig(config_path=config_path)
            guard = SafetyGuard(config=config)
            yield guard

    def test_delete_transaction_rollback(self, temp_guard):
        """Test rollback info for delete_transaction."""
        params = {"transaction_id": "txn_123"}
        rollback = temp_guard._generate_rollback_info(
            "delete_transaction", params, None
        )

        assert rollback["reversible"] is True
        assert rollback["reverse_operation"] == "create_transaction"
        assert rollback["deleted_id"] == "txn_123"

    def test_create_transaction_rollback(self, temp_guard):
        """Test rollback info for create_transaction."""
        params = {"account_id": "acc_123", "amount": 50.00}
        result = json.dumps({"id": "txn_new_456"})
        rollback = temp_guard._generate_rollback_info(
            "create_transaction", params, result
        )

        assert rollback["reversible"] is True
        assert rollback["reverse_operation"] == "delete_transaction"
        assert rollback["created_id"] == "txn_new_456"

    def test_update_transaction_rollback(self, temp_guard):
        """Test rollback info for update_transaction."""
        params = {
            "transaction_id": "txn_123",
            "amount": 75.00,
            "description": "New desc",
        }
        rollback = temp_guard._generate_rollback_info(
            "update_transaction", params, None
        )

        assert rollback["reversible"] is True
        assert rollback["reverse_operation"] == "update_transaction"
        assert rollback["modified_id"] == "txn_123"
        assert "amount" in rollback["modified_fields"]
        assert "description" in rollback["modified_fields"]

    def test_unknown_operation_rollback(self, temp_guard):
        """Test rollback info for unknown operation."""
        params = {"some_param": "value"}
        rollback = temp_guard._generate_rollback_info("unknown_operation", params, None)

        assert rollback["reversible"] is False


class TestDestructiveOperationBehavior:
    """Tests for destructive operation handling (Claude Code manages user approval)."""

    @pytest.fixture
    def temp_guard(self):
        """Create a SafetyGuard with temporary files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "safety_config.json")
            config = SafetyConfig(config_path=config_path)
            guard = SafetyGuard(config=config)
            guard.operation_log_path = str(Path(tmpdir) / "operation_log.json")
            yield guard

    def test_destructive_op_allowed_with_warning(self, temp_guard):
        """Test that destructive operations are allowed (Claude Code handles approval)."""
        temp_guard.config.config["require_approval"] = ["test_destructive_op"]

        operation_details = {"some_id": "123"}
        allowed, message = temp_guard.check_operation(
            "test_destructive_op", operation_details
        )

        # Should be allowed - Claude Code prompts user for approval
        assert allowed is True
        assert "destructive" in message.lower()

    def test_destructive_op_blocked_by_emergency_stop(self, temp_guard):
        """Test that emergency stop blocks destructive operations."""
        temp_guard.config.config["require_approval"] = ["test_destructive_op"]
        temp_guard.config.config["emergency_stop"] = True

        operation_details = {"some_id": "123"}
        allowed, message = temp_guard.check_operation(
            "test_destructive_op", operation_details
        )

        assert allowed is False
        assert "EMERGENCY STOP" in message

    @pytest.mark.asyncio
    async def test_decorator_allows_destructive_ops(self, temp_guard):
        """Test decorator allows destructive operations (Claude Code handles approval)."""
        guard = get_safety_guard()
        original_approval = guard.config.config.get("require_approval", [])
        guard.config.config["require_approval"] = ["decorator_test_op"]

        try:

            @require_safety_check("decorator_test_op")
            async def destructive_func(item_id: str):
                return f"Deleted {item_id}"

            result = await destructive_func("item_123")
            assert result == "Deleted item_123"

        finally:
            guard.config.config["require_approval"] = original_approval

    def test_non_destructive_op_allowed(self, temp_guard):
        """Test that non-destructive read operations are allowed."""
        temp_guard.config.config["require_approval"] = ["delete_something"]

        operation_details = {"some_id": "123"}
        allowed, message = temp_guard.check_operation("get_accounts", operation_details)

        assert allowed is True
        assert "Operation allowed" in message
