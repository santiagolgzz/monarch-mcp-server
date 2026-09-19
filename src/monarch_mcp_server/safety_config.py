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
                "update_transaction_splits",
                "create_manual_account",
                "update_account",
                "set_budget_amount",
                "add_transaction_tag",
                "categorize_transaction",
                "upload_attachment",
            ],
            "emergency_stop": False,
            "enabled": True,
            # Two-step confirmation for the require_approval list. This is what
            # makes that list mean something — before it existed, "approval"
            # operations ran exactly like warned ones. Set False to restore the
            # old warn-and-proceed behavior.
            "require_confirmation": True,
            "confirmation_ttl_seconds": 300,
            # Per-operation ceilings on successful writes per day. Counts were
            # already tracked and reported; nothing enforced them, so a runaway
            # caller was caught only by a human noticing. Generous by default —
            # these stop runaway loops, not bulk work. null means no limit.
            "daily_limits": {
                "delete_transaction": 50,
                "delete_account": 5,
                "delete_transaction_category": 25,
                "delete_transaction_categories": 5,
                "upload_account_balance_history": 10,
                "create_transaction": 200,
                "update_transaction": 200,
            },
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

    def confirmation_enabled(self) -> bool:
        """Whether require_approval operations need a confirmation token."""
        return bool(self.config.get("require_confirmation", True))

    def confirmation_ttl(self) -> int:
        """How long a confirmation token stays valid, in seconds."""
        try:
            ttl = int(self.config.get("confirmation_ttl_seconds", 300))
        except (TypeError, ValueError):
            return 300
        return ttl if ttl > 0 else 300

    def daily_limit(self, operation_name: str) -> int | None:
        """Successful writes allowed per day, or None when uncapped."""
        limits = self.config.get("daily_limits") or {}
        limit = limits.get(operation_name)
        if limit is None:
            return None
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return None
        return limit if limit >= 0 else None
