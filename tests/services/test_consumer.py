import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infraestructure.mensageria.base import BrokerMessage
from schemas.message import AgentMessage, AgentType
from services.consumer import MessageConsumer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_broker_msg(
    payload: dict | None = None, body: str | None = None
) -> BrokerMessage:
    if body is None:
        payload = payload or {
            "prompt": "recommend me something",
            "agent_type": "default",
        }
        body = json.dumps(payload)
    return BrokerMessage(body=body, message_id="broker-raw-id")


def _make_agent_msg(**kwargs) -> AgentMessage:
    defaults = {"prompt": "recommend me something", "agent_type": AgentType.DEFAULT}
    defaults.update(kwargs)
    return AgentMessage(**defaults)


def _make_redis() -> MagicMock:
    redis = MagicMock()
    redis.__aenter__ = AsyncMock(return_value=redis)
    redis.__aexit__ = AsyncMock()
    redis.set_if_not_exists = AsyncMock(return_value=True)  # new by default
    redis.set_status = AsyncMock()
    return redis


def _make_broker(*messages: BrokerMessage) -> MagicMock:
    """Broker that yields the given messages then stops."""
    broker = MagicMock()
    broker.__aenter__ = AsyncMock(return_value=broker)
    broker.__aexit__ = AsyncMock()
    broker.ack = AsyncMock()
    broker.nack = AsyncMock()

    async def _consume():
        for m in messages:
            yield m

    broker.consume = MagicMock(return_value=_consume())
    return broker


def _make_consumer(broker, redis, max_concurrency: int = 10) -> MessageConsumer:
    return MessageConsumer(broker=broker, redis=redis, max_concurrency=max_concurrency)


# ---------------------------------------------------------------------------
# _handle — invalid JSON / schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_json_is_nacked_to_dlq():
    broker_msg = _make_broker_msg(body="not-json-at-all")
    broker = _make_broker(broker_msg)
    redis = _make_redis()
    consumer = _make_consumer(broker, redis)

    with patch("services.consumer.agent_with_mcp", new=AsyncMock()):
        await consumer.start()

    broker.nack.assert_awaited_once_with(broker_msg, requeue=False)
    broker.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_prompt_is_nacked_to_dlq():
    broker_msg = _make_broker_msg({"prompt": "", "agent_type": "default"})
    broker = _make_broker(broker_msg)
    redis = _make_redis()
    consumer = _make_consumer(broker, redis)

    with patch("services.consumer.agent_with_mcp", new=AsyncMock()):
        await consumer.start()

    broker.nack.assert_awaited_once_with(broker_msg, requeue=False)


# ---------------------------------------------------------------------------
# _handle — deduplication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_message_is_acked_and_skipped():
    broker_msg = _make_broker_msg()
    broker = _make_broker(broker_msg)
    redis = _make_redis()
    redis.set_if_not_exists = AsyncMock(return_value=False)  # duplicate

    agent_mock = AsyncMock()
    consumer = _make_consumer(broker, redis)

    with patch("services.consumer.agent_with_mcp", new=agent_mock):
        await consumer.start()

    broker.ack.assert_awaited_once_with(broker_msg)
    agent_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_dedup_key_uses_message_id(monkeypatch):
    msg = _make_agent_msg()
    broker_msg = _make_broker_msg(body=msg.model_dump_json())
    broker = _make_broker(broker_msg)
    redis = _make_redis()
    consumer = _make_consumer(broker, redis)

    with patch("services.consumer.agent_with_mcp", new=AsyncMock()):
        await consumer.start()

    call_args = redis.set_if_not_exists.call_args
    assert call_args.args[0] == f"dedup:{msg.message_id}"


# ---------------------------------------------------------------------------
# _handle — status tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_set_to_processing_before_dispatch():
    msg = _make_agent_msg()
    broker_msg = _make_broker_msg(body=msg.model_dump_json())
    broker = _make_broker(broker_msg)
    redis = _make_redis()
    consumer = _make_consumer(broker, redis)

    call_order = []
    redis.set_status = AsyncMock(side_effect=lambda *a, **kw: call_order.append(a[1]))

    with patch("services.consumer.agent_with_mcp", new=AsyncMock()):
        await consumer.start()

    assert call_order[0] == "processing"


@pytest.mark.asyncio
async def test_status_set_to_done_after_success():
    msg = _make_agent_msg()
    broker_msg = _make_broker_msg(body=msg.model_dump_json())
    broker = _make_broker(broker_msg)
    redis = _make_redis()
    consumer = _make_consumer(broker, redis)

    statuses = []
    redis.set_status = AsyncMock(side_effect=lambda *a, **kw: statuses.append(a[1]))

    with patch("services.consumer.agent_with_mcp", new=AsyncMock()):
        await consumer.start()

    assert "done" in statuses


@pytest.mark.asyncio
async def test_status_set_to_failed_on_exception():
    msg = _make_agent_msg()
    broker_msg = _make_broker_msg(body=msg.model_dump_json())
    broker = _make_broker(broker_msg)
    redis = _make_redis()
    consumer = _make_consumer(broker, redis)

    statuses = []
    redis.set_status = AsyncMock(side_effect=lambda *a, **kw: statuses.append(a[1]))

    with patch(
        "services.consumer.agent_with_mcp",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        await consumer.start()

    assert "failed" in statuses


# ---------------------------------------------------------------------------
# _dispatch — routing by agent_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_agent_type_calls_agent_with_mcp():
    msg = _make_agent_msg(agent_type=AgentType.DEFAULT)
    broker_msg = _make_broker_msg(body=msg.model_dump_json())
    broker = _make_broker(broker_msg)
    redis = _make_redis()
    consumer = _make_consumer(broker, redis)

    agent_mock = AsyncMock()
    with (
        patch("services.consumer.agent_with_mcp", new=agent_mock),
        patch("services.consumer.agent_recommendation_products", new=AsyncMock()),
    ):
        await consumer.start()

    agent_mock.assert_awaited_once_with(msg.prompt)


@pytest.mark.asyncio
async def test_recommendation_products_agent_type_calls_correct_service():
    msg = _make_agent_msg(agent_type=AgentType.RECOMMENDATION_PRODUCTS)
    broker_msg = _make_broker_msg(body=msg.model_dump_json())
    broker = _make_broker(broker_msg)
    redis = _make_redis()
    consumer = _make_consumer(broker, redis)

    rec_mock = AsyncMock()
    with (
        patch("services.consumer.agent_with_mcp", new=AsyncMock()),
        patch("services.consumer.agent_recommendation_products", new=rec_mock),
    ):
        await consumer.start()

    rec_mock.assert_awaited_once_with(msg.prompt)


# ---------------------------------------------------------------------------
# _dispatch — ack / nack
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_dispatch_acks_message():
    broker_msg = _make_broker_msg()
    broker = _make_broker(broker_msg)
    redis = _make_redis()
    consumer = _make_consumer(broker, redis)

    with patch("services.consumer.agent_with_mcp", new=AsyncMock()):
        await consumer.start()

    broker.ack.assert_awaited_once_with(broker_msg)
    broker.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_dispatch_nacks_to_dlq():
    broker_msg = _make_broker_msg()
    broker = _make_broker(broker_msg)
    redis = _make_redis()
    consumer = _make_consumer(broker, redis)

    with patch(
        "services.consumer.agent_with_mcp",
        new=AsyncMock(side_effect=RuntimeError("agent failure")),
    ):
        await consumer.start()

    broker.nack.assert_awaited_once_with(broker_msg, requeue=False)
    broker.ack.assert_not_awaited()


# ---------------------------------------------------------------------------
# Concurrency — semaphore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_semaphore_limits_concurrent_dispatch():
    """With max_concurrency=1 messages are processed sequentially."""
    call_log = []

    async def slow_agent(prompt):
        call_log.append("start")
        await asyncio.sleep(0)
        call_log.append("end")

    msgs = [
        _make_broker_msg({"prompt": f"p{i}", "agent_type": "default"}) for i in range(3)
    ]
    broker = _make_broker(*msgs)
    redis = _make_redis()
    consumer = _make_consumer(broker, redis, max_concurrency=1)

    with patch("services.consumer.agent_with_mcp", new=slow_agent):
        await consumer.start()

    # With semaphore=1, processing is sequential: start→end repeats
    for i in range(0, len(call_log) - 1, 2):
        assert call_log[i] == "start"
        assert call_log[i + 1] == "end"


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_sets_shutdown_event():
    consumer = MessageConsumer(
        broker=MagicMock(), redis=MagicMock(), max_concurrency=10
    )
    assert not consumer._shutdown_event.is_set()
    await consumer.stop()
    assert consumer._shutdown_event.is_set()


@pytest.mark.asyncio
async def test_drain_waits_for_active_tasks():
    consumer = MessageConsumer(
        broker=MagicMock(), redis=MagicMock(), max_concurrency=10
    )
    completed = []

    async def slow():
        await asyncio.sleep(0)
        completed.append(True)

    task = asyncio.create_task(slow())
    consumer._active_tasks.add(task)
    task.add_done_callback(consumer._active_tasks.discard)

    await consumer._drain()
    assert completed == [True]
