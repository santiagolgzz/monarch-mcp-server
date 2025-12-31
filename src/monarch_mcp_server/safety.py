"""Safety module for Monarch MCP Server - User Approval Based."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class SafetyConfig:
    """Configuration for safety protections."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize safety configuration."""
        self.config_path = config_path or str(
            Path.home() / ".mm" / "safety_config.json"
        )
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load safety configuration from file or use defaults."""
        default_config = {
            # Operations requiring user approval (will prompt in Claude Desktop)
            "require_approval": [
                "delete_transaction",
                "delete_account",
                "delete_transaction_category",
                "delete_transaction_categories",
                "upload_account_balance_history",
            ],
            # Operations that will show warnings but don't require approval
            "warn_before_execute": [
                "create_transaction",
                "update_transaction",
                "create_manual_account",
                "update_account",
                "set_budget_amount",
            ],
            # Emergency stop - disable all write operations
            "emergency_stop": False,
            # Enable safety features
            "enabled": True,
        }

        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, "r") as f:
                    loaded_config = json.load(f)
                # Merge with defaults
                for key in default_config:
                    if key not in loaded_config:
                        loaded_config[key] = default_config[key]
                return loaded_config
        except Exception as e:
            logger.warning(f"Failed to load safety config, using defaults: {e}")

        return default_config

    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            config_file = Path(self.config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, "w") as f:
                json.dump(self.config, indent=2, fp=f)
        except Exception as e:
            logger.error(f"Failed to save safety config: {e}")

    def requires_approval(self, operation_name: str) -> bool:
        """Check if operation requires user approval."""
        return operation_name in self.config.get("require_approval", [])

    def should_warn(self, operation_name: str) -> bool:
        """Check if operation should show warning."""
        return operation_name in self.config.get("warn_before_execute", [])


class SafetyGuard:
    """Safety guard using user approval model."""

    def __init__(self, config: Optional[SafetyConfig] = None):
        """Initialize safety guard."""
        self.config = config or SafetyConfig()
        self.operation_log_path = str(Path.home() / ".mm" / "operation_log.json")

        # Track operations for statistics
        self.daily_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._load_operation_log()

    def _load_operation_log(self) -> None:
        """Load operation history."""
        try:
            log_file = Path(self.operation_log_path)
            if log_file.exists():
                with open(log_file, "r") as f:
                    data = json.load(f)
                    today = datetime.now().strftime("%Y-%m-%d")
                    if today in data:
                        self.daily_counts[today] = defaultdict(int, data[today].get("counts", {}))
        except Exception as e:
            logger.warning(f"Failed to load operation log: {e}")

    def _save_operation_log(self) -> None:
        """Save operation history."""
        try:
            log_file = Path(self.operation_log_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing
            data = {}
            if log_file.exists():
                with open(log_file, "r") as f:
                    data = json.load(f)

            # Update today
            today = datetime.now().strftime("%Y-%m-%d")
            data[today] = {
                "counts": dict(self.daily_counts[today]),
                "last_updated": datetime.now().isoformat(),
            }

            with open(log_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save operation log: {e}")

    def check_operation(
        self, operation_name: str, operation_details: Optional[Dict] = None
    ) -> tuple[bool, str]:
        """
        Check if operation is allowed.

        Returns:
            Tuple of (allowed: bool, message: str)
        """
        if not self.config.config.get("enabled", True):
            return True, "Safety checks disabled"

        # Emergency stop check
        if self.config.config.get("emergency_stop", False):
            return (
                False,
                f"🚨 EMERGENCY STOP ACTIVE: All write operations disabled.\n"
                f"Use disable_emergency_stop() to re-enable or edit {self.config.config_path}",
            )

        # Check if approval required
        if self.config.requires_approval(operation_name):
            # Only enforce confirmed check if the parameter exists in operation_details
            # This allows custom operations added to require_approval to still work
            # even if they don't have a confirmed parameter
            if operation_details and "confirmed" in operation_details:
                if not operation_details["confirmed"]:
                    return (
                        False,
                        f"⚠️  This is a destructive operation requiring approval. Set 'confirmed=True' to execute.",
                    )
                return True, "Operation confirmed and allowed"
            else:
                # No confirmed parameter - allow with warning for backwards compatibility
                # This handles custom operations added to require_approval
                return (
                    True,
                    f"⚠️  Destructive operation '{operation_name}' requires approval. "
                    f"Consider adding 'confirmed' parameter for explicit confirmation.",
                )

        # Just informational warning
        if self.config.should_warn(operation_name):
            return True, f"ℹ️  Executing write operation: {operation_name}"

        return True, "Operation allowed"

    def record_operation(
        self,
        operation_name: str,
        success: bool = True,
        operation_details: Optional[Dict] = None,
        result: Optional[str] = None,
    ) -> None:
        """
        Record that an operation was performed with full details for rollback.

        Args:
            operation_name: Name of the operation
            success: Whether operation succeeded
            operation_details: Dict of parameters passed to operation
            result: Result returned from operation (for extracting IDs)
        """
        if success:
            today = datetime.now().strftime("%Y-%m-%d")
            self.daily_counts[today][operation_name] += 1

            # Save detailed operation log for rollback
            self._save_detailed_operation(operation_name, operation_details, result)
            self._save_operation_log()

    def _save_detailed_operation(
        self,
        operation_name: str,
        operation_details: Optional[Dict],
        result: Optional[str],
    ) -> None:
        """Save detailed operation log for potential rollback."""
        try:
            detailed_log_path = str(
                Path.home() / ".mm" / "detailed_operation_log.jsonl"
            )
            log_file = Path(detailed_log_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            # Create log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation_name,
                "parameters": operation_details or {},
                "result_preview": result[:500] if result else None,  # First 500 chars
                "rollback_info": self._generate_rollback_info(
                    operation_name, operation_details, result
                ),
            }

            # Append to JSONL file (one JSON object per line)
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")

        except Exception as e:
            logger.error(f"Failed to save detailed operation log: {e}")

    def _generate_rollback_info(
        self, operation_name: str, params: Optional[Dict], result: Optional[str]
    ) -> Dict:
        """Generate rollback information for an operation."""
        rollback = {"reversible": False, "reverse_operation": None, "notes": ""}

        if not params:
            return rollback

        # Delete operations - save what was deleted for recreation
        if operation_name == "delete_transaction":
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "create_transaction",
                    "notes": f"To recreate: Use transaction details from get_transaction_details({params.get('transaction_id')})",
                    "deleted_id": params.get("transaction_id"),
                }
            )

        elif operation_name == "delete_account":
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "create_manual_account",
                    "notes": f"To recreate: Use account details from get_accounts before deletion",
                    "deleted_id": params.get("account_id"),
                }
            )

        elif operation_name == "delete_transaction_category":
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "create_transaction_category",
                    "notes": f"To recreate: Use category details from get_transaction_categories before deletion",
                    "deleted_id": params.get("category_id"),
                }
            )

        elif operation_name == "delete_transaction_categories":
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "create_transaction_category (multiple)",
                    "notes": f"To recreate: Use category details from get_transaction_categories before deletion",
                    "deleted_ids": params.get("category_ids", "").split(","),
                }
            )

        # Update operations - save original values
        elif operation_name == "update_transaction":
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "update_transaction",
                    "notes": f"To undo: Get original values from transaction history",
                    "modified_id": params.get("transaction_id"),
                    "modified_fields": {
                        k: v
                        for k, v in params.items()
                        if k != "transaction_id" and v is not None
                    },
                }
            )

        elif operation_name == "update_account":
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "update_account",
                    "notes": f"To undo: Get original values from account history",
                    "modified_id": params.get("account_id"),
                    "modified_fields": {
                        k: v
                        for k, v in params.items()
                        if k != "account_id" and v is not None
                    },
                }
            )

        # Create operations - save created ID for deletion
        elif operation_name == "create_transaction":
            # Try to extract ID from result
            created_id = self._extract_id_from_result(result)
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "delete_transaction",
                    "notes": "To undo: Delete the created transaction",
                    "created_id": created_id,
                    "creation_params": params,
                }
            )

        elif operation_name == "create_manual_account":
            created_id = self._extract_id_from_result(result)
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "delete_account",
                    "notes": "To undo: Delete the created account",
                    "created_id": created_id,
                    "creation_params": params,
                }
            )

        elif operation_name == "create_transaction_category":
            created_id = self._extract_id_from_result(result)
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "delete_transaction_category",
                    "notes": "To undo: Delete the created category",
                    "created_id": created_id,
                    "creation_params": params,
                }
            )

        return rollback

    def _extract_id_from_result(self, result: Optional[str]) -> Optional[str]:
        """Try to extract an ID from operation result."""
        if not result:
            return None
        try:
            result_data = json.loads(result)
            # Common ID field names
            for id_field in ["id", "transaction_id", "account_id", "category_id"]:
                if id_field in result_data:
                    return str(result_data[id_field])
        except:
            pass
        return None

    def get_operation_stats(self) -> Dict:
        """Get operation statistics for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        return {
            "date": today,
            "operations_today": dict(self.daily_counts[today]),
            "total_operations_today": sum(self.daily_counts[today].values()),
            "emergency_stop": self.config.config.get("emergency_stop", False),
            "approval_required_for": self.config.config.get("require_approval", []),
        }

    def enable_emergency_stop(self) -> str:
        """Enable emergency stop."""
        self.config.config["emergency_stop"] = True
        self.config.save_config()
        logger.critical("🚨 EMERGENCY STOP ACTIVATED")
        return "🚨 Emergency stop activated. All write operations are now disabled."

    def disable_emergency_stop(self) -> str:
        """Disable emergency stop."""
        self.config.config["emergency_stop"] = False
        self.config.save_config()
        logger.info("✅ Emergency stop deactivated")
        return "✅ Emergency stop deactivated. Write operations are now enabled."


# Global instance
_safety_guard: Optional[SafetyGuard] = None


def get_safety_guard() -> SafetyGuard:
    """Get or create the global safety guard instance."""
    global _safety_guard
    if _safety_guard is None:
        _safety_guard = SafetyGuard()
    return _safety_guard


def require_safety_check(operation_name: str):
    """
    Decorator to add safety checks and detailed logging to write operations.

    For destructive operations in require_approval list, Claude Desktop's
    approval system will automatically prompt the user.

    Logs all parameters and results for potential rollback.
    """

    def decorator(func):
        import functools
        import inspect

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            guard = get_safety_guard()

            # Retrieve all arguments including defaults
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            operation_details = dict(bound_args.arguments)

            # Check if operation is allowed
            allowed, message = guard.check_operation(operation_name, operation_details)
            if not allowed:
                logger.warning(f"Operation '{operation_name}' blocked: {message}")
                return json.dumps(
                    {"error": "Operation blocked", "reason": message}, indent=2
                )

            # Log informational message if needed
            if message and message != "Operation allowed":
                logger.info(f"{operation_name}: {message}")

            # Execute operation
            try:
                result = func(*args, **kwargs)

                # Record operation
                guard.record_operation(
                    operation_name,
                    success=True,
                    operation_details=operation_details,
                    result=result,
                )
                return result
            except Exception as e:
                guard.record_operation(operation_name, success=False)
                raise

        return wrapper

    return decorator
