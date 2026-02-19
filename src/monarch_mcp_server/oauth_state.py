"""OAuth state storage and self-repair helpers for MCP HTTP server."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from key_value.aio.stores.redis import RedisStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

OAUTH_REDIS_URL_ENV = "MCP_OAUTH_REDIS_URL"
OAUTH_JWT_SIGNING_KEY_ENV = "MCP_OAUTH_JWT_SIGNING_KEY"

_VOLATILE_COLLECTIONS = (
    "mcp-oauth-transactions",
    "mcp-authorization-codes",
    "mcp-jti-mappings",
)


@dataclass
class RepairStatus:
    ok: bool
    message: str
    at_unix: float


class OAuthStateManager:
    """Tracks OAuth storage health and performs controlled auto-repair."""

    def __init__(self) -> None:
        self.storage: Any | None = None
        self._storage_key: tuple[str, str] | None = None
        self._invalid_token_events: deque[float] = deque()
        self._repair_lock = asyncio.Lock()
        self._last_repair: RepairStatus | None = None

    def configure_storage(self, redis_url: str, signing_key: str) -> Any:
        """Build (or reuse) encrypted Redis-backed OAuth storage."""
        cache_key = (redis_url, signing_key)
        if self.storage is not None and self._storage_key == cache_key:
            return self.storage

        redis_store = RedisStore(url=redis_url)
        self.storage = FernetEncryptionWrapper(
            key_value=redis_store,
            source_material=signing_key,
            salt="monarch-mcp-oauth-storage-v1",
        )
        self._storage_key = cache_key
        return self.storage

    def disable_storage(self) -> None:
        """Disable managed Redis storage and clear related in-memory state."""
        self.storage = None
        self._storage_key = None
        self._last_repair = None
        self.reset_events()

    def reset_events(self) -> None:
        self._invalid_token_events.clear()

    def mark_invalid_token(self, *, now: float | None = None) -> bool:
        """Record an invalid token event and report if repair threshold is reached."""
        now = now or time.time()
        self._invalid_token_events.append(now)
        self._prune_old(now)
        return len(self._invalid_token_events) >= 3

    @property
    def invalid_token_rate_1m(self) -> int:
        self._prune_old(time.time())
        return len(self._invalid_token_events)

    @property
    def last_repair(self) -> RepairStatus | None:
        return self._last_repair

    async def probe_storage(self) -> tuple[bool, str]:
        """Write/read/delete sentinel key to verify store health."""
        if self.storage is None:
            return False, "oauth storage not configured"

        probe_key = f"health:{time.time_ns()}"
        try:
            await self.storage.put(
                probe_key,
                {"ok": True},
                collection="mcp-oauth-health",
                ttl=60,
            )
            result = await self.storage.get(probe_key, collection="mcp-oauth-health")
            await self.storage.delete(probe_key, collection="mcp-oauth-health")
            if not result or not result.get("ok"):
                return False, "oauth storage probe readback failed"
            return True, "ok"
        except Exception as exc:
            return False, f"oauth storage probe failed: {exc}"

    async def repair(self) -> RepairStatus:
        """Purge volatile OAuth proxy collections and re-probe storage."""
        async with self._repair_lock:
            if self.storage is None:
                status = RepairStatus(False, "oauth storage unavailable", time.time())
                self._last_repair = status
                return status

            try:
                for collection in _VOLATILE_COLLECTIONS:
                    if hasattr(self.storage, "destroy_collection"):
                        await self.storage.destroy_collection(collection)
                        continue

                    if hasattr(self.storage, "keys") and hasattr(
                        self.storage, "delete_many"
                    ):
                        keys = await self.storage.keys(
                            collection=collection, limit=5000
                        )
                        if keys:
                            await self.storage.delete_many(keys, collection=collection)

                probe_ok, probe_msg = await self.probe_storage()
                status = RepairStatus(
                    ok=probe_ok,
                    message="repair complete" if probe_ok else probe_msg,
                    at_unix=time.time(),
                )
            except Exception as exc:
                status = RepairStatus(False, f"repair failed: {exc}", time.time())

            self._last_repair = status
            if status.ok:
                self.reset_events()
            return status

    def _prune_old(self, now: float) -> None:
        cutoff = now - 60.0
        while self._invalid_token_events and self._invalid_token_events[0] < cutoff:
            self._invalid_token_events.popleft()


oauth_state_manager = OAuthStateManager()
