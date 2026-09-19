"""Tests for the safety module."""

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

    def test_add_transaction_tag_in_warn_list(self):
        """Test that add_transaction_tag is in warn_before_execute list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            config = SafetyConfig(config_path=config_path)

            assert config.should_warn("add_transaction_tag") is True

    def test_categorize_transaction_in_warn_list(self):
        """Test that categorize_transaction is in warn_before_execute list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test_config.json")
            config = SafetyConfig(config_path=config_path)

            assert config.should_warn("categorize_transaction") is True

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
            result_data = result

            assert "error" in result_data
            assert "blocked" in result_data["error"]  # type: ignore[index]
            assert "EMERGENCY STOP" in result_data["reason"]  # type: ignore[index]
        finally:
            guard.config.config["emergency_stop"] = original_stop

    @pytest.mark.asyncio
    async def test_decorator_records_failure_and_reraises(self):
        """Test decorator records failure and re-raises when function throws."""
        guard = get_safety_guard()
        original_enabled = guard.config.config.get("enabled", True)
        guard.config.config["enabled"] = False

        # Track if record_operation was called with success=False
        recorded_failures = []
        original_record = guard.record_operation

        def mock_record(op_name, success=True, **kwargs):
            if not success:
                recorded_failures.append(op_name)
            return original_record(op_name, success=success, **kwargs)

        try:

            @require_safety_check("failing_op")
            async def failing_func():
                raise ValueError("Intentional test error")

            guard.record_operation = mock_record  # type: ignore[assignment]

            with pytest.raises(ValueError, match="Intentional test error"):
                await failing_func()

            # Verify failure was recorded
            assert "failing_op" in recorded_failures

        finally:
            guard.config.config["enabled"] = original_enabled
            guard.record_operation = original_record  # type: ignore[assignment]


class TestRequireSafetyCheckSyncPath:
    """Tests for sync function support in require_safety_check decorator."""

    @pytest.mark.asyncio
    async def test_sync_function_works(self):
        """Test decorator works with synchronous functions."""
        guard = get_safety_guard()
        original_enabled = guard.config.config.get("enabled", True)
        guard.config.config["enabled"] = False

        try:

            @require_safety_check("sync_test_op")
            def sync_func(value: str) -> str:
                return f"Result: {value}"

            # The decorator returns an async wrapper, so we need to await it
            result = await sync_func("test")  # type: ignore[misc]
            assert result == "Result: test"

        finally:
            guard.config.config["enabled"] = original_enabled

    @pytest.mark.asyncio
    async def test_sync_function_records_operation(self):
        """Test decorator records operations for sync functions."""
        from collections import defaultdict

        guard = get_safety_guard()
        original_enabled = guard.config.config.get("enabled", True)
        guard.config.config["enabled"] = False

        # Reset counts for this test
        original_counts = guard.daily_counts
        guard.daily_counts = defaultdict(lambda: defaultdict(int))

        try:

            @require_safety_check("sync_recorded_op")
            def sync_func():
                return "done"

            await sync_func()  # type: ignore[misc]

            today = datetime.now().strftime("%Y-%m-%d")
            assert guard.daily_counts[today]["sync_recorded_op"] == 1

        finally:
            guard.config.config["enabled"] = original_enabled
            guard.daily_counts = original_counts


class TestGenerateRollbackInfo:
    """Rollback planning moved to ``monarch_mcp_server.rollback``.

    These tests asserted a bare ``reversible: True`` against flat result
    shapes the SDK never returns, which is what let the broken ID extraction
    ship. ``tests/test_rollback.py`` covers the same ground against the real
    envelopes in ``tests/sdk_fixtures.py``.
    """

    def test_planning_is_covered_in_test_rollback(self):
        from monarch_mcp_server.rollback import build_rollback

        from . import sdk_fixtures

        plan = build_rollback(
            "create_transaction",
            {"account_id": "acc_1"},
            sdk_fixtures.create_transaction_response("txn_1"),
        )
        assert plan["reverse_call"] == {
            "tool": "delete_transaction",
            "arguments": {"transaction_id": "txn_1"},
        }


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

    def test_check_operation_flags_destructive_ops_but_does_not_gate_them(
        self, temp_guard
    ):
        """check_operation warns; confirm_operation is what actually gates.

        This used to be the whole story, and it was the bug behind issue #20:
        an operation named require_approval executed exactly like a warned one.
        """
        temp_guard.config.config["require_approval"] = ["test_destructive_op"]

        allowed, message = temp_guard.check_operation(
            "test_destructive_op", {"some_id": "123"}
        )

        assert allowed is True
        assert "destructive" in message.lower()

    async def test_destructive_op_requires_confirmation(self, temp_guard):
        """The gate that issue #20 said was missing."""
        temp_guard.config.config["require_approval"] = ["test_destructive_op"]

        params = {"some_id": "123"}
        confirmed, refusal = await temp_guard.confirm_operation(
            "test_destructive_op", params, None
        )

        assert confirmed is False
        assert refusal["error"] == "Confirmation required"

        token = refusal["confirmation_token"]
        confirmed, refusal = await temp_guard.confirm_operation(
            "test_destructive_op", {**params, "confirmation_token": token}, None
        )
        assert confirmed is True
        assert refusal is None

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
    async def test_decorator_gates_destructive_ops_behind_confirmation(
        self, temp_guard
    ):
        """The decorator withholds a destructive op until it is confirmed."""
        guard = get_safety_guard()
        original_approval = guard.config.config.get("require_approval", [])
        guard.config.config["require_approval"] = ["decorator_test_op"]

        calls: list[str] = []

        try:

            @require_safety_check("decorator_test_op")
            async def destructive_func(item_id: str, confirmation_token=None):
                calls.append(item_id)
                return f"Deleted {item_id}"

            challenge = await destructive_func("item_123")
            assert challenge["error"] == "Confirmation required"
            assert not calls, "the operation must not run before confirmation"

            result = await destructive_func(
                "item_123", confirmation_token=challenge["confirmation_token"]
            )
            assert result == "Deleted item_123"
            assert calls == ["item_123"]

        finally:
            guard.config.config["require_approval"] = original_approval

    @pytest.mark.asyncio
    async def test_decorator_runs_destructive_ops_when_gate_is_disabled(
        self, temp_guard
    ):
        """Operators can opt back into warn-and-proceed."""
        guard = get_safety_guard()
        original_approval = guard.config.config.get("require_approval", [])
        original_confirm = guard.config.config.get("require_confirmation", True)
        guard.config.config["require_approval"] = ["decorator_test_op"]
        guard.config.config["require_confirmation"] = False

        try:

            @require_safety_check("decorator_test_op")
            async def destructive_func(item_id: str):
                return f"Deleted {item_id}"

            assert await destructive_func("item_123") == "Deleted item_123"
        finally:
            guard.config.config["require_approval"] = original_approval
            guard.config.config["require_confirmation"] = original_confirm

    def test_non_destructive_op_allowed(self, temp_guard):
        """Test that non-destructive read operations are allowed."""
        temp_guard.config.config["require_approval"] = ["delete_something"]

        operation_details = {"some_id": "123"}
        allowed, message = temp_guard.check_operation("get_accounts", operation_details)

        assert allowed is True
        assert "Operation allowed" in message
