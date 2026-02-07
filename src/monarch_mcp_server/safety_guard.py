"""Safety guard implementation with rollback-aware operation logging."""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from monarch_mcp_server.paths import mm_file
from monarch_mcp_server.safety_config import SafetyConfig

logger = logging.getLogger(__name__)


class SafetyGuard:
    """Safety guard using user approval model."""

    def __init__(self, config: SafetyConfig | None = None):
        """Initialize safety guard."""
        self.config = config or SafetyConfig()
        self.operation_log_path = str(mm_file("operation_log.json"))
        self.daily_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._load_operation_log()

    def _load_operation_log(self) -> None:
        """Load operation history."""
        try:
            log_file = Path(self.operation_log_path)
            if log_file.exists():
                with open(log_file) as f:
                    data = json.load(f)
                    today = datetime.now().strftime("%Y-%m-%d")
                    if today in data:
                        self.daily_counts[today] = defaultdict(
                            int, data[today].get("counts", {})
                        )
        except Exception as e:
            logger.warning(f"Failed to load operation log: {e}")

    def _save_operation_log(self) -> None:
        """Save operation history."""
        try:
            log_file = Path(self.operation_log_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if log_file.exists():
                with open(log_file) as f:
                    data = json.load(f)

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
        self, operation_name: str, operation_details: dict | None = None
    ) -> tuple[bool, str]:
        """Check if operation is allowed."""
        _ = operation_details
        if not self.config.config.get("enabled", True):
            return True, "Safety checks disabled"

        if self.config.config.get("emergency_stop", False):
            return (
                False,
                f"🚨 EMERGENCY STOP ACTIVE: All write operations disabled.\n"
                f"Use disable_emergency_stop() to re-enable or edit {self.config.config_path}",
            )

        if self.config.requires_approval(operation_name):
            return True, f"⚠️  Destructive operation: {operation_name}"

        if self.config.should_warn(operation_name):
            return True, f"ℹ️  Executing write operation: {operation_name}"

        return True, "Operation allowed"

    def record_operation(
        self,
        operation_name: str,
        success: bool = True,
        operation_details: dict | None = None,
        result: Any = None,
    ) -> None:
        """Record that an operation was performed with full details for rollback."""
        if success:
            today = datetime.now().strftime("%Y-%m-%d")
            self.daily_counts[today][operation_name] += 1
            self._save_detailed_operation(operation_name, operation_details, result)
            self._save_operation_log()

    def _save_detailed_operation(
        self,
        operation_name: str,
        operation_details: dict | None,
        result: Any,
    ) -> None:
        """Save detailed operation log for potential rollback."""
        try:
            log_file = mm_file("detailed_operation_log.jsonl")
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation_name,
                "parameters": operation_details or {},
                "result_preview": self._preview_result(result),
                "rollback_info": self._generate_rollback_info(
                    operation_name, operation_details, result
                ),
            }
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to save detailed operation log: {e}")

    def _generate_rollback_info(
        self, operation_name: str, params: dict | None, result: Any
    ) -> dict:
        """Generate rollback information for an operation."""
        rollback = {"reversible": False, "reverse_operation": None, "notes": ""}

        if not params:
            return rollback

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
                    "notes": "To recreate: Use account details from get_accounts before deletion",
                    "deleted_id": params.get("account_id"),
                }
            )
        elif operation_name == "delete_transaction_category":
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "create_transaction_category",
                    "notes": "To recreate: Use category details from get_transaction_categories before deletion",
                    "deleted_id": params.get("category_id"),
                }
            )
        elif operation_name == "delete_transaction_categories":
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "create_transaction_category (multiple)",
                    "notes": "To recreate: Use category details from get_transaction_categories before deletion",
                    "deleted_ids": [
                        id.strip() for id in params.get("category_ids", "").split(",")
                    ],
                }
            )
        elif operation_name == "update_transaction":
            rollback.update(
                {
                    "reversible": True,
                    "reverse_operation": "update_transaction",
                    "notes": "To undo: Get original values from transaction history",
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
                    "notes": "To undo: Get original values from account history",
                    "modified_id": params.get("account_id"),
                    "modified_fields": {
                        k: v
                        for k, v in params.items()
                        if k != "account_id" and v is not None
                    },
                }
            )
        elif operation_name == "create_transaction":
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

    def _preview_result(self, result: Any) -> str | None:
        """Build a compact preview string for operation logs."""
        if result is None:
            return None

        if isinstance(result, str):
            return result[:500]

        try:
            return json.dumps(result, default=str)[:500]
        except (TypeError, ValueError):
            return str(result)[:500]

    def _extract_id_from_result(self, result: Any) -> str | None:
        """Try to extract an ID from operation result."""
        if result is None:
            return None

        if isinstance(result, dict):
            for id_field in ["id", "transaction_id", "account_id", "category_id"]:
                if id_field in result and result[id_field] is not None:
                    return str(result[id_field])
            return None

        try:
            result_data = json.loads(result) if isinstance(result, str) else result
            if not isinstance(result_data, dict):
                return None
            for id_field in ["id", "transaction_id", "account_id", "category_id"]:
                if id_field in result_data and result_data[id_field] is not None:
                    return str(result_data[id_field])
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        return None

    def get_operation_stats(self) -> dict:
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
