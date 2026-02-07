"""Safety configuration model for write-operation protections."""

import json
import logging
from pathlib import Path

from monarch_mcp_server.paths import mm_file

logger = logging.getLogger(__name__)


class SafetyConfig:
    """Configuration for safety protections."""

    def __init__(self, config_path: str | None = None):
        """Initialize safety configuration."""
        self.config_path = config_path or str(mm_file("safety_config.json"))
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load safety configuration from file or use defaults."""
        default_config = {
            "require_approval": [
                "delete_transaction",
                "delete_account",
                "delete_transaction_category",
                "delete_transaction_categories",
                "upload_account_balance_history",
            ],
            "warn_before_execute": [
                "create_transaction",
                "update_transaction",
                "create_manual_account",
                "update_account",
                "set_budget_amount",
            ],
            "emergency_stop": False,
            "enabled": True,
        }

        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file) as f:
                    loaded_config = json.load(f)
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
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save safety config: {e}")

    def requires_approval(self, operation_name: str) -> bool:
        """Check if operation requires user approval."""
        return operation_name in self.config.get("require_approval", [])

    def should_warn(self, operation_name: str) -> bool:
        """Check if operation should show warning."""
        return operation_name in self.config.get("warn_before_execute", [])
