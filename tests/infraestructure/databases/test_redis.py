import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infraestructure.databases.redis import RedisDatabase


REDIS_URL = "redis://:password@localhost:6379/0"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_client():
    client = MagicMock()
    client.aclose = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.setex = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=0)
    client.ping = AsyncMock(return_value=True)
    return client


def _make_mock_pool():
    pool = MagicMock()
    pool.aclose = AsyncMock()
    return pool


@pytest.fixture
def mock_client():
    return _make_mock_client()


@pytest.fixture
def mock_pool():
    return _make_mock_pool()


@pytest.fixture
async def db(mock_client, mock_pool):
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis", return_value=mock_client),
    ):
        async with RedisDatabase(url=REDIS_URL) as redis_db:
            yield redis_db


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_creates_pool_and_client(mock_client, mock_pool):
    with (
        patch(
            "redis.asyncio.ConnectionPool.from_url", return_value=mock_pool
        ) as pool_mock,
        patch("redis.asyncio.Redis", return_value=mock_client) as client_mock,
    ):
        db = RedisDatabase(url=REDIS_URL)
        await db.connect()
        pool_mock.assert_called_once_with(
            REDIS_URL,
            max_connections=20,
            decode_responses=True,
        )
        client_mock.assert_called_once_with(connection_pool=mock_pool)
        await db.disconnect()


@pytest.mark.asyncio
async def test_disconnect_closes_client_and_pool(db, mock_client, mock_pool):
    await db.disconnect()
    mock_client.aclose.assert_awaited_once()
    mock_pool.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_disconnect_sets_client_and_pool_to_none(db):
    await db.disconnect()
    assert db._client is None
    assert db._pool is None


@pytest.mark.asyncio
async def test_disconnect_idempotent_when_not_connected():
    db = RedisDatabase(url=REDIS_URL)
    await db.disconnect()  # must not raise


@pytest.mark.asyncio
async def test_context_manager_connects_and_disconnects(mock_client, mock_pool):
    with (
        patch("redis.asyncio.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis", return_value=mock_client),
    ):
        async with RedisDatabase(url=REDIS_URL) as redis_db:
            assert redis_db._client is not None
        mock_client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# _get_client guard
# ---------------------------------------------------------------------------


def test_get_client_raises_if_not_connected():
    db = RedisDatabase(url=REDIS_URL)
    with pytest.raises(RuntimeError, match="not initialised"):
        db._get_client()


# ---------------------------------------------------------------------------
# get / set / delete / exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_value(db, mock_client):
    mock_client.get.return_value = "hello"
    result = await db.get("mykey")
    mock_client.get.assert_awaited_once_with("mykey")
    assert result == "hello"


@pytest.mark.asyncio
async def test_get_returns_none_when_absent(db, mock_client):
    mock_client.get.return_value = None
    result = await db.get("missing")
    assert result is None


@pytest.mark.asyncio
async def test_set_without_ttl(db, mock_client):
    await db.set("k", "v")
    mock_client.set.assert_awaited_once_with("k", "v")


@pytest.mark.asyncio
async def test_set_with_ttl_uses_setex(db, mock_client):
    await db.set("k", "v", ttl_seconds=300)
    mock_client.setex.assert_awaited_once_with("k", 300, "v")


@pytest.mark.asyncio
async def test_delete_calls_delete(db, mock_client):
    await db.delete("k")
    mock_client.delete.assert_awaited_once_with("k")


@pytest.mark.asyncio
async def test_exists_returns_true(db, mock_client):
    mock_client.exists.return_value = 1
    assert await db.exists("k") is True


@pytest.mark.asyncio
async def test_exists_returns_false(db, mock_client):
    mock_client.exists.return_value = 0
    assert await db.exists("k") is False


# ---------------------------------------------------------------------------
# set_if_not_exists — deduplication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_if_not_exists_first_time_returns_true(db, mock_client):
    mock_client.set.return_value = True
    result = await db.set_if_not_exists("idempotency:abc", "1")
    mock_client.set.assert_awaited_once_with("idempotency:abc", "1", nx=True, ex=86_400)
    assert result is True


@pytest.mark.asyncio
async def test_set_if_not_exists_duplicate_returns_false(db, mock_client):
    mock_client.set.return_value = None  # Redis returns None on SETNX fail
    result = await db.set_if_not_exists("idempotency:abc", "1")
    assert result is False


@pytest.mark.asyncio
async def test_set_if_not_exists_custom_ttl(db, mock_client):
    mock_client.set.return_value = True
    await db.set_if_not_exists("k", "v", ttl_seconds=3600)
    mock_client.set.assert_awaited_once_with("k", "v", nx=True, ex=3600)


# ---------------------------------------------------------------------------
# get_json / set_json
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_json_returns_deserialized_value(db, mock_client):
    mock_client.get.return_value = json.dumps({"status": "ok"})
    result = await db.get_json("k")
    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_get_json_returns_none_when_absent(db, mock_client):
    mock_client.get.return_value = None
    result = await db.get_json("k")
    assert result is None


@pytest.mark.asyncio
async def test_set_json_serializes_and_stores(db, mock_client):
    payload = {"agent": "default", "score": 0.95}
    await db.set_json("k", payload)
    mock_client.set.assert_awaited_once_with("k", json.dumps(payload, default=str))


@pytest.mark.asyncio
async def test_set_json_with_ttl(db, mock_client):
    await db.set_json("k", {"x": 1}, ttl_seconds=60)
    mock_client.setex.assert_awaited_once_with(
        "k", 60, json.dumps({"x": 1}, default=str)
    )


# ---------------------------------------------------------------------------
# set_status / get_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_status_uses_correct_key(db, mock_client):
    await db.set_status("msg-123", "processing")
    mock_client.setex.assert_awaited_once_with("status:msg-123", 3600, "processing")


@pytest.mark.asyncio
async def test_get_status_uses_correct_key(db, mock_client):
    mock_client.get.return_value = "done"
    result = await db.get_status("msg-123")
    mock_client.get.assert_awaited_once_with("status:msg-123")
    assert result == "done"


@pytest.mark.asyncio
async def test_get_status_returns_none_when_absent(db, mock_client):
    mock_client.get.return_value = None
    result = await db.get_status("msg-999")
    assert result is None


# ---------------------------------------------------------------------------
# ping / health check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ping_returns_true_when_healthy(db, mock_client):
    mock_client.ping.return_value = True
    assert await db.ping() is True


@pytest.mark.asyncio
async def test_ping_returns_false_on_exception(db, mock_client):
    mock_client.ping.side_effect = Exception("connection refused")
    assert await db.ping() is False


# ---------------------------------------------------------------------------
# Custom pool settings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_custom_max_connections(mock_client, mock_pool):
    with (
        patch(
            "redis.asyncio.ConnectionPool.from_url", return_value=mock_pool
        ) as pool_mock,
        patch("redis.asyncio.Redis", return_value=mock_client),
    ):
        db = RedisDatabase(url=REDIS_URL, max_connections=50)
        await db.connect()
        pool_mock.assert_called_once_with(
            REDIS_URL,
            max_connections=50,
            decode_responses=True,
        )
        await db.disconnect()
