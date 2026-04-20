import json
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RedisDatabase:
    """Async Redis client backed by a connection pool.

    Responsibilities in the pub/sub pipeline:
      - Deduplication  : ``set_if_not_exists`` (SETNX + TTL)
      - Response cache : ``get`` / ``set`` with optional TTL
      - Job state      : ``set_status`` / ``get_status``

    Usage::

        async with RedisDatabase(url="redis://:password@host:6379/0") as redis:
            cached = await redis.get("key")
    """

    def __init__(
        self,
        url: str,
        max_connections: int = 20,
        decode_responses: bool = True,
    ) -> None:
        self._url = url
        self._max_connections = max_connections
        self._decode_responses = decode_responses
        self._pool: aioredis.ConnectionPool | None = None
        self._client: aioredis.Redis | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        self._pool = aioredis.ConnectionPool.from_url(
            self._url,
            max_connections=self._max_connections,
            decode_responses=self._decode_responses,
        )
        self._client = aioredis.Redis(connection_pool=self._pool)
        logger.info(
            "Redis connection pool created (max_connections=%d)", self._max_connections
        )

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._pool:
            await self._pool.aclose()
            self._pool = None
        logger.info("Redis connection pool closed")

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "RedisDatabase":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("Redis client is not initialised. Call connect() first.")
        return self._client

    # ------------------------------------------------------------------
    # Basic key/value
    # ------------------------------------------------------------------

    async def get(self, key: str) -> str | None:
        """Return the string value for *key*, or ``None`` if absent."""
        return await self._get_client().get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Set *key* to *value*.  Optionally expire after *ttl_seconds*."""
        client = self._get_client()
        if ttl_seconds is not None:
            await client.setex(key, ttl_seconds, value)
        else:
            await client.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete *key* (no-op if absent)."""
        await self._get_client().delete(key)

    async def exists(self, key: str) -> bool:
        """Return ``True`` if *key* exists."""
        return bool(await self._get_client().exists(key))

    # ------------------------------------------------------------------
    # Deduplication — idempotency key
    # ------------------------------------------------------------------

    async def set_if_not_exists(
        self,
        key: str,
        value: str,
        ttl_seconds: int = 86_400,
    ) -> bool:
        """Atomic SETNX with TTL. Returns ``True`` if the key was set
        (first time seen), ``False`` if it already existed (duplicate).

        Used to deduplicate messages arriving from SQS / RabbitMQ.
        TTL defaults to 24 h so the idempotency store self-cleans.
        """
        client = self._get_client()
        result = await client.set(key, value, nx=True, ex=ttl_seconds)
        return result is True

    # ------------------------------------------------------------------
    # JSON helpers — cache LLM responses
    # ------------------------------------------------------------------

    async def get_json(self, key: str) -> Any | None:
        """Return a deserialized JSON value, or ``None`` if absent."""
        raw = await self.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """Serialize *value* as JSON and store it under *key*."""
        await self.set(key, json.dumps(value, default=str), ttl_seconds)

    # ------------------------------------------------------------------
    # Job state — track processing status per message_id
    # ------------------------------------------------------------------

    async def set_status(
        self,
        message_id: str,
        status: str,
        ttl_seconds: int = 3_600,
    ) -> None:
        """Store a processing status string for *message_id*.
        TTL defaults to 1 h.
        """
        await self.set(f"status:{message_id}", status, ttl_seconds)

    async def get_status(self, message_id: str) -> str | None:
        """Return the processing status for *message_id*, or ``None``."""
        return await self.get(f"status:{message_id}")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Return ``True`` if the Redis server is reachable."""
        try:
            return await self._get_client().ping()
        except Exception:
            return False
