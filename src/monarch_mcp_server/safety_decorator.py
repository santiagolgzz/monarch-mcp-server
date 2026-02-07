"""Decorator helpers for safety checks around write operations."""

import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any

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
                )
                return result
            except Exception:
                guard.record_operation(operation_name, success=False)
                raise

        return wrapper

    return decorator
