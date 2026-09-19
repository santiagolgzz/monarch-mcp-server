"""Decorator helpers for safety checks around write operations."""

import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any

from monarch_mcp_server.pre_state import capture as capture_pre_state

logger = logging.getLogger(__name__)


def require_safety_check(
    operation_name: str, get_safety_guard: Callable[[], Any]
) -> Callable:
    """
    Decorator factory to add safety checks and operation logging.

    The `get_safety_guard` callback is injected so callers can keep patch-friendly
    behavior and avoid hard-coding global singleton imports.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            guard = get_safety_guard()

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            operation_details = dict(bound_args.arguments)

            allowed, message = guard.check_operation(operation_name, operation_details)
            if not allowed:
                logger.warning(f"Operation '{operation_name}' blocked: {message}")
                return {"error": "Operation blocked", "reason": message}

            if message and message != "Operation allowed":
                logger.info(f"{operation_name}: {message}")

            # Snapshot before the write, since the write is what destroys the
            # values an undo would need. Best-effort: a failed capture is
            # recorded and the operation still runs.
            pre_state, capture_error = await capture_pre_state(
                operation_name, operation_details
            )

            # The confirmation gate runs after capture so the challenge can
            # describe the record that is about to be destroyed. A token the
            # caller cannot evaluate would be a rubber stamp.
            confirmed, refusal = guard.confirm_operation(
                operation_name, operation_details, pre_state
            )
            if not confirmed:
                return refusal

            try:
                if inspect.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                guard.record_operation(
                    operation_name,
                    success=True,
                    operation_details=operation_details,
                    result=result,
                    pre_state=pre_state,
                    pre_state_error=capture_error,
                )
                return result
            except Exception as exc:
                # Record the failure before re-raising. A write that raised may
                # still have applied, so this is the entry an operator most
                # needs; dropping it is how a partial change goes unnoticed.
                guard.record_operation(
                    operation_name,
                    success=False,
                    operation_details=operation_details,
                    error=f"{type(exc).__name__}: {exc}",
                    pre_state=pre_state,
                    pre_state_error=capture_error,
                )
                raise

        return wrapper

    return decorator
