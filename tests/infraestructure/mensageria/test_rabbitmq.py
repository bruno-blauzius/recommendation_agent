import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from infraestructure.mensageria.base import BrokerMessage
from infraestructure.mensageria.rabbitmq import RabbitMQAdapter


AMQP_URL = "amqp://guest:guest@localhost/"
QUEUE = "agent.tasks"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_message(body: str = '{"prompt": "hello"}', message_id: str = "msg-1"):
    raw = MagicMock()
    raw.body = body.encode()
    raw.headers = {"x-source": "test"}
    raw.message_id = message_id
    raw.ack = AsyncMock()
    raw.nack = AsyncMock()
    return raw


def _make_channel(closed: bool = False):
    channel = MagicMock()
    type(channel).is_closed = PropertyMock(return_value=closed)
    channel.set_qos = AsyncMock()
    channel.declare_queue = AsyncMock()
    channel.close = AsyncMock()
    channel.get_exchange = AsyncMock()
    channel.default_exchange = MagicMock()
    channel.default_exchange.publish = AsyncMock()
    return channel


def _make_connection(closed: bool = False):
    conn = MagicMock()
    type(conn).is_closed = PropertyMock(return_value=closed)
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def mock_channel():
    return _make_channel()


@pytest.fixture
def mock_connection():
    return _make_connection()


@pytest.fixture
async def adapter(mock_connection, mock_channel):
    mock_queue = AsyncMock()
    mock_channel.declare_queue.return_value = mock_queue

    with patch("aio_pika.connect_robust", new=AsyncMock(return_value=mock_connection)):
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        a = RabbitMQAdapter(url=AMQP_URL, queue_name=QUEUE)
        await a.connect()
        yield a


# ---------------------------------------------------------------------------
# Lifecycle — connect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_creates_robust_connection(mock_connection, mock_channel):
    mock_channel.declare_queue.return_value = AsyncMock()
    with patch(
        "aio_pika.connect_robust", new=AsyncMock(return_value=mock_connection)
    ) as conn_mock:
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        a = RabbitMQAdapter(url=AMQP_URL, queue_name=QUEUE)
        await a.connect()
        conn_mock.assert_awaited_once_with(AMQP_URL)


@pytest.mark.asyncio
async def test_connect_sets_qos_with_prefetch_count(mock_connection, mock_channel):
    mock_channel.declare_queue.return_value = AsyncMock()
    with patch("aio_pika.connect_robust", new=AsyncMock(return_value=mock_connection)):
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        a = RabbitMQAdapter(url=AMQP_URL, queue_name=QUEUE, prefetch_count=5)
        await a.connect()
        mock_channel.set_qos.assert_awaited_once_with(prefetch_count=5)


@pytest.mark.asyncio
async def test_connect_declares_durable_queue(mock_connection, mock_channel):
    mock_channel.declare_queue.return_value = AsyncMock()
    with patch("aio_pika.connect_robust", new=AsyncMock(return_value=mock_connection)):
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        a = RabbitMQAdapter(url=AMQP_URL, queue_name=QUEUE)
        await a.connect()
        mock_channel.declare_queue.assert_awaited_once_with(
            QUEUE, durable=True, arguments=None
        )


@pytest.mark.asyncio
async def test_connect_declares_queue_with_dlx(mock_connection, mock_channel):
    mock_channel.declare_queue.return_value = AsyncMock()
    with patch("aio_pika.connect_robust", new=AsyncMock(return_value=mock_connection)):
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        a = RabbitMQAdapter(
            url=AMQP_URL, queue_name=QUEUE, dead_letter_exchange="agent.dlx"
        )
        await a.connect()
        call_kwargs = mock_channel.declare_queue.call_args.kwargs
        assert call_kwargs["arguments"] == {"x-dead-letter-exchange": "agent.dlx"}


# ---------------------------------------------------------------------------
# Lifecycle — disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disconnect_closes_channel_and_connection(
    adapter, mock_channel, mock_connection
):
    await adapter.disconnect()
    mock_channel.close.assert_awaited_once()
    mock_connection.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_disconnect_sets_internals_to_none(adapter):
    await adapter.disconnect()
    assert adapter._channel is None
    assert adapter._connection is None
    assert adapter._queue is None


@pytest.mark.asyncio
async def test_disconnect_idempotent_when_not_connected():
    a = RabbitMQAdapter(url=AMQP_URL, queue_name=QUEUE)
    await a.disconnect()  # must not raise


@pytest.mark.asyncio
async def test_disconnect_skips_closed_channel(mock_connection):
    closed_channel = _make_channel(closed=True)
    closed_channel.declare_queue.return_value = AsyncMock()
    with patch("aio_pika.connect_robust", new=AsyncMock(return_value=mock_connection)):
        mock_connection.channel = AsyncMock(return_value=closed_channel)
        a = RabbitMQAdapter(url=AMQP_URL, queue_name=QUEUE)
        await a.connect()
        await a.disconnect()
        closed_channel.close.assert_not_awaited()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_manager_calls_connect_and_disconnect(
    mock_connection, mock_channel
):
    mock_channel.declare_queue.return_value = AsyncMock()
    with patch("aio_pika.connect_robust", new=AsyncMock(return_value=mock_connection)):
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        a = RabbitMQAdapter(url=AMQP_URL, queue_name=QUEUE)
        async with a:
            assert a._channel is not None
        mock_channel.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def test_get_channel_raises_when_not_connected():
    a = RabbitMQAdapter(url=AMQP_URL, queue_name=QUEUE)
    with pytest.raises(RuntimeError, match="not open"):
        a._get_channel()


def test_get_queue_raises_when_not_connected():
    a = RabbitMQAdapter(url=AMQP_URL, queue_name=QUEUE)
    with pytest.raises(RuntimeError, match="not declared"):
        a._get_queue()


def test_get_queue_returns_queue_when_connected(adapter):
    # Line 107: return self._queue (happy path)
    q = adapter._get_queue()
    assert q is adapter._queue


# ---------------------------------------------------------------------------
# ack / nack
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ack_calls_raw_ack(adapter):
    raw = _make_raw_message()
    msg = BrokerMessage(body=raw.body.decode(), raw=raw, message_id=raw.message_id)
    await adapter.ack(msg)
    raw.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_nack_requeue_true(adapter):
    raw = _make_raw_message()
    msg = BrokerMessage(body=raw.body.decode(), raw=raw, message_id=raw.message_id)
    await adapter.nack(msg, requeue=True)
    raw.nack.assert_awaited_once_with(requeue=True)


@pytest.mark.asyncio
async def test_nack_requeue_false_routes_to_dlq(adapter):
    raw = _make_raw_message()
    msg = BrokerMessage(body=raw.body.decode(), raw=raw, message_id=raw.message_id)
    await adapter.nack(msg, requeue=False)
    raw.nack.assert_awaited_once_with(requeue=False)


# ---------------------------------------------------------------------------
# publish — default exchange
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_uses_default_exchange_when_no_exchange_name(
    adapter, mock_channel
):
    await adapter.publish(body='{"ok": true}', routing_key="result.queue")
    mock_channel.default_exchange.publish.assert_awaited_once()
    call_args = mock_channel.default_exchange.publish.call_args
    assert call_args.kwargs["routing_key"] == "result.queue"


@pytest.mark.asyncio
async def test_publish_encodes_body_as_bytes(adapter, mock_channel):
    await adapter.publish(body="hello world", routing_key="rk")
    published_msg = mock_channel.default_exchange.publish.call_args.args[0]
    assert published_msg.body == b"hello world"


@pytest.mark.asyncio
async def test_publish_uses_persistent_delivery_mode(adapter, mock_channel):
    import aio_pika

    await adapter.publish(body="msg", routing_key="rk")
    published_msg = mock_channel.default_exchange.publish.call_args.args[0]
    assert published_msg.delivery_mode == aio_pika.DeliveryMode.PERSISTENT


@pytest.mark.asyncio
async def test_publish_uses_named_exchange(mock_connection, mock_channel):
    mock_exchange = MagicMock()
    mock_exchange.publish = AsyncMock()
    mock_channel.get_exchange.return_value = mock_exchange
    mock_channel.declare_queue.return_value = AsyncMock()

    with patch("aio_pika.connect_robust", new=AsyncMock(return_value=mock_connection)):
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        a = RabbitMQAdapter(
            url=AMQP_URL, queue_name=QUEUE, exchange_name="agent.exchange"
        )
        await a.connect()
        await a.publish(body="msg", routing_key="rk")
        mock_channel.get_exchange.assert_awaited_once_with("agent.exchange")
        mock_exchange.publish.assert_awaited_once()


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ping_returns_true_when_healthy(adapter):
    assert await adapter.ping() is True


@pytest.mark.asyncio
async def test_ping_returns_false_when_not_connected():
    a = RabbitMQAdapter(url=AMQP_URL, queue_name=QUEUE)
    assert await a.ping() is False


@pytest.mark.asyncio
async def test_ping_returns_false_after_disconnect(adapter):
    await adapter.disconnect()
    assert await adapter.ping() is False


@pytest.mark.asyncio
async def test_ping_returns_false_on_exception(adapter, mock_connection):
    type(mock_connection).is_closed = PropertyMock(side_effect=Exception("boom"))
    assert await adapter.ping() is False


# ---------------------------------------------------------------------------
# consume — async iterator / BrokerMessage mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consume_yields_broker_message_with_correct_fields(adapter):
    """Lines 119-121: async for loop yields BrokerMessage mapped from raw message."""
    raw = _make_raw_message(body='{"prompt": "test"}', message_id="id-42")
    raw.headers = {"x-retry": "1"}

    async def _iter():
        yield raw

    queue_mock = MagicMock()
    queue_mock.iterator.return_value.__aenter__ = AsyncMock(return_value=_iter())
    queue_mock.iterator.return_value.__aexit__ = AsyncMock(return_value=False)
    adapter._queue = queue_mock

    messages = []
    async for msg in adapter.consume():
        messages.append(msg)
        break  # one message is enough

    assert len(messages) == 1
    m = messages[0]
    assert m.body == '{"prompt": "test"}'
    assert m.message_id == "id-42"
    assert m.headers == {"x-retry": "1"}
    assert m.raw is raw


@pytest.mark.asyncio
async def test_consume_yields_multiple_messages_in_order(adapter):
    """consume() yields all messages from the queue in order."""
    raws = [_make_raw_message(body=f"msg-{i}", message_id=f"id-{i}") for i in range(3)]

    async def _iter():
        for r in raws:
            yield r

    queue_mock = MagicMock()
    queue_mock.iterator.return_value.__aenter__ = AsyncMock(return_value=_iter())
    queue_mock.iterator.return_value.__aexit__ = AsyncMock(return_value=False)
    adapter._queue = queue_mock

    received = []
    async for msg in adapter.consume():
        received.append(msg)

    assert [m.message_id for m in received] == ["id-0", "id-1", "id-2"]


@pytest.mark.asyncio
async def test_consume_handles_none_headers(adapter):
    """headers=None in raw message → empty dict in BrokerMessage."""
    raw = _make_raw_message()
    raw.headers = None

    async def _iter():
        yield raw

    queue_mock = MagicMock()
    queue_mock.iterator.return_value.__aenter__ = AsyncMock(return_value=_iter())
    queue_mock.iterator.return_value.__aexit__ = AsyncMock(return_value=False)
    adapter._queue = queue_mock

    messages = []
    async for msg in adapter.consume():
        messages.append(msg)

    assert messages[0].headers == {}


# ---------------------------------------------------------------------------
# BrokerMessage
# ---------------------------------------------------------------------------


def test_broker_message_defaults():
    msg = BrokerMessage(body="hello")
    assert msg.body == "hello"
    assert msg.headers == {}
    assert msg.message_id is None
    assert msg.raw is None


def test_broker_message_stores_all_fields():
    raw = object()
    msg = BrokerMessage(
        body="body",
        headers={"x-retry": "2"},
        message_id="abc-123",
        raw=raw,
    )
    assert msg.headers == {"x-retry": "2"}
    assert msg.message_id == "abc-123"
    assert msg.raw is raw
