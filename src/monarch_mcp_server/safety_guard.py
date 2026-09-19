"""Safety guard implementation with rollback-aware operation logging."""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from monarch_mcp_server.approval import ApprovalStore, preview_of
from monarch_mcp_server.paths import mm_file
from monarch_mcp_server.rollback import build_rollback
from monarch_mcp_server.safety_config import SafetyConfig

logger = logging.getLogger(__name__)

# Parameters whose values must never reach the audit log verbatim. Two reasons:
# a base64 attachment or a balance-history CSV would bloat every line and put a
# second copy of the file on disk, and a confirmation token is a capability —
# logging it would let anyone who can read the log replay a destructive call.
_REDACTED_PARAMS = {
    "file_content_base64": "content",
    "csv_data": "content",
    "confirmation_token": "secret",
}

# Long free-text values are truncated rather than dropped, so the audit trail
# keeps enough to identify the record without storing the whole payload.
_MAX_LOGGED_VALUE_CHARS = 500


def _redact(params: dict) -> dict:
    """Strip oversized and sensitive values from parameters before logging."""
    redacted: dict[str, Any] = {}
    for key, value in params.items():
        kind = _REDACTED_PARAMS.get(key)
        if kind == "secret":
            redacted[key] = "<redacted>"
        elif kind == "content":
            size = len(value) if isinstance(value, str | bytes) else 0
            redacted[key] = f"<redacted: {size} bytes>"
        elif isinstance(value, str) and len(value) > _MAX_LOGGED_VALUE_CHARS:
            kept = value[:_MAX_LOGGED_VALUE_CHARS]
            redacted[key] = f"{kept}… <truncated, {len(value)} chars total>"
        else:
            redacted[key] = value
    return redacted


class SafetyGuard:
    """Safety guard using user approval model."""

    def __init__(self, config: SafetyConfig | None = None):
        """Initialize safety guard."""
        self.config = config or SafetyConfig()
        self.operation_log_path = str(mm_file("operation_log.json"))
        self.daily_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self.approvals = ApprovalStore(ttl_seconds=self.config.confirmation_ttl())
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

        # Daily ceilings. These were counted and reported but never enforced,
        # so a runaway caller was stopped only by a human noticing and hitting
        # the emergency stop.
        limit = self.config.daily_limit(operation_name)
        if limit is not None:
            today = datetime.now().strftime("%Y-%m-%d")
            used = self.daily_counts[today].get(operation_name, 0)
            if used >= limit:
                return (
                    False,
                    f"Daily limit reached for {operation_name}: {used}/{limit} "
                    f"already succeeded today. This exists to stop runaway "
                    f"loops. Raise 'daily_limits.{operation_name}' in "
                    f"{self.config.config_path} if this is deliberate work.",
                )

        if self.config.requires_approval(operation_name):
            return True, f"⚠️  Destructive operation: {operation_name}"

        if self.config.should_warn(operation_name):
            return True, f"ℹ️  Executing write operation: {operation_name}"

        return True, "Operation allowed"

    def confirm_operation(
        self,
        operation_name: str,
        params: dict,
        pre_state: dict | None,
    ) -> tuple[bool, dict | None]:
        """Apply the two-step confirmation gate.

        Returns ``(allowed, refusal)``. The refusal is the challenge to hand
        back to the caller, carrying a token and a description of the record
        about to be destroyed.
        """
        if not self.config.requires_approval(operation_name):
            return True, None

        if not self.config.confirmation_enabled():
            return True, None

        token = params.get("confirmation_token")
        if token:
            accepted, reason = self.approvals.redeem(token, operation_name, params)
            if accepted:
                logger.info("Confirmation accepted for %s", operation_name)
                return True, None
            logger.warning("Confirmation rejected for %s: %s", operation_name, reason)
            return False, {
                "error": "Confirmation rejected",
                "operation": operation_name,
                "reason": reason,
            }

        challenge = self.approvals.issue(
            operation_name,
            params,
            preview_of(operation_name, params, pre_state),
        )
        return False, challenge.as_response()

    def record_operation(
        self,
        operation_name: str,
        success: bool = True,
        operation_details: dict | None = None,
        result: Any = None,
        pre_state: dict | None = None,
        pre_state_error: str | None = None,
        error: str | None = None,
    ) -> None:
        """Record that an operation was attempted.

        Failures are recorded too. A write that raised may still have applied
        partially, so leaving it out of the audit log is exactly the case an
        operator most needs to see. Only successes count toward the daily
        totals, which drive the caps in ``check_operation``.
        """
        if success:
            today = datetime.now().strftime("%Y-%m-%d")
            self.daily_counts[today][operation_name] += 1
            self._save_operation_log()

        self._save_detailed_operation(
            operation_name,
            operation_details,
            result,
            success=success,
            pre_state=pre_state,
            pre_state_error=pre_state_error,
            error=error,
        )

    def _save_detailed_operation(
        self,
        operation_name: str,
        operation_details: dict | None,
        result: Any,
        *,
        success: bool = True,
        pre_state: dict | None = None,
        pre_state_error: str | None = None,
        error: str | None = None,
    ) -> None:
        """Save detailed operation log for potential rollback."""
        try:
            log_file = mm_file("detailed_operation_log.jsonl")
            log_file.parent.mkdir(parents=True, exist_ok=True)
            # Redact before planning too: a rollback record echoes the call's
            # parameters back for context, which would otherwise smuggle the
            # very payloads the redaction exists to keep out of the log. The
            # reverse call itself is built from pre_state and IDs, never from
            # the redacted values, so planning is unaffected.
            safe_params = _redact(operation_details or {})
            log_entry: dict[str, Any] = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation_name,
                "success": success,
                "parameters": safe_params,
                "result_preview": self._preview_result(result),
                "pre_state": pre_state,
                "rollback_info": build_rollback(
                    operation_name, safe_params, result, pre_state
                ),
            }
            if pre_state_error:
                # Say why the undo is unavailable, rather than leaving a bare
                # "no snapshot was captured" that reads like it was never tried.
                log_entry["pre_state_error"] = pre_state_error
                log_entry["rollback_info"]["blocked_reason"] = (
                    f"Capturing a pre-operation snapshot failed "
                    f"({pre_state_error}), so this operation cannot be reversed "
                    "from the log."
                )
            if not success:
                log_entry["error"] = error
                # A failed call may still have applied. Say so rather than
                # letting the rollback plan imply the change definitely landed.
                log_entry["rollback_info"] = {
                    "reversible": False,
                    "reverse_operation": None,
                    "reverse_call": None,
                    "notes": "",
                    "blocked_reason": (
                        f"{operation_name} raised before completing, so whether "
                        "it applied is unknown. Verify the record's current "
                        "state in Monarch before attempting any correction."
                    ),
                }
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to save detailed operation log: {e}")

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

    def get_operation_stats(self) -> dict:
        """Get operation statistics for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        return {
            "date": today,
            "operations_today": dict(self.daily_counts[today]),
            "total_operations_today": sum(self.daily_counts[today].values()),
            "emergency_stop": self.config.config.get("emergency_stop", False),
            "confirmation_required": self.config.confirmation_enabled(),
            "approval_required_for": self.config.config.get("require_approval", []),
            "pending_confirmations": self.approvals.pending_count(),
            "daily_limits": self.config.config.get("daily_limits", {}),
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
