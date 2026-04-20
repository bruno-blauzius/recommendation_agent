import logging
from collections.abc import AsyncIterator
from typing import Any

import aio_pika
import aio_pika.abc

from infraestructure.mensageria.base import BrokerAdapter, BrokerMessage

logger = logging.getLogger(__name__)


class RabbitMQAdapter(BrokerAdapter):
    """RabbitMQ adapter built on top of ``aio-pika``.

    Supports:
    - Durable queues with dead-letter exchange (DLX) configuration
    - QoS / prefetch count for backpressure
    - Manual ack/nack so the consumer loop controls delivery guarantees
    - Publishing to any routing key on the default or a named exchange

    Configuration example::

        adapter = RabbitMQAdapter(
            url="amqp://guest:guest@localhost/",
            queue_name="agent.tasks",
            prefetch_count=10,
            dead_letter_exchange="agent.dlx",
        )

    Dead-letter exchange setup (optional but recommended for production)::

        If *dead_letter_exchange* is provided the queue is declared with
        the ``x-dead-letter-exchange`` argument so that nack'd messages
        with ``requeue=False`` are automatically routed to the DLX
        instead of being discarded.
    """

    def __init__(
        self,
        url: str,
        queue_name: str,
        prefetch_count: int = 10,
        exchange_name: str = "",
        dead_letter_exchange: str | None = None,
    ) -> None:
        self._url = url
        self._queue_name = queue_name
        self._prefetch_count = prefetch_count
        self._exchange_name = exchange_name
        self._dead_letter_exchange = dead_letter_exchange

        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._queue: aio_pika.abc.AbstractQueue | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open a robust connection (auto-reconnects on network failures)
        and declare the queue if it does not yet exist.
        """
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._prefetch_count)

        queue_args: dict[str, Any] = {}
        if self._dead_letter_exchange:
            queue_args["x-dead-letter-exchange"] = self._dead_letter_exchange

        self._queue = await self._channel.declare_queue(
            self._queue_name,
            durable=True,
            arguments=queue_args or None,
        )
        logger.info(
            "RabbitMQ connected — queue=%s prefetch=%d",
            self._queue_name,
            self._prefetch_count,
        )

    async def disconnect(self) -> None:
        """Close channel and connection gracefully."""
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
            self._channel = None
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            self._connection = None
        self._queue = None
        logger.info("RabbitMQ connection closed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_channel(self) -> aio_pika.abc.AbstractChannel:
        if self._channel is None or self._channel.is_closed:
            raise RuntimeError("RabbitMQ channel is not open. Call connect() first.")
        return self._channel

    def _get_queue(self) -> aio_pika.abc.AbstractQueue:
        if self._queue is None:
            raise RuntimeError("RabbitMQ queue is not declared. Call connect() first.")
        return self._queue

    # ------------------------------------------------------------------
    # Consuming
    # ------------------------------------------------------------------

    async def consume(self) -> AsyncIterator[BrokerMessage]:
        """Yield messages from the queue using an async iterator.

        Each yielded message must be explicitly ack'd or nack'd by the
        caller — no automatic acknowledgement is applied.
        """
        async with self._get_queue().iterator() as queue_iter:
            async for raw_message in queue_iter:
                yield BrokerMessage(
                    body=raw_message.body.decode(),
                    headers=dict(raw_message.headers or {}),
                    message_id=raw_message.message_id,
                    raw=raw_message,
                )

    async def ack(self, message: BrokerMessage) -> None:
        """Acknowledge *message* — removes it from the queue."""
        raw: aio_pika.abc.AbstractIncomingMessage = message.raw
        await raw.ack()
        logger.debug("ACK — message_id=%s", message.message_id)

    async def nack(self, message: BrokerMessage, requeue: bool = True) -> None:
        """Reject *message*.

        Args:
            requeue: ``True``  → message returns to the queue head.
                     ``False`` → message is routed to the DLX (if configured)
                                 or discarded.
        """
        raw: aio_pika.abc.AbstractIncomingMessage = message.raw
        await raw.nack(requeue=requeue)
        logger.debug("NACK — message_id=%s requeue=%s", message.message_id, requeue)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(
        self,
        body: str,
        routing_key: str,
        headers: dict[str, Any] | None = None,
    ) -> None:
        """Publish *body* as a persistent message.

        Uses ``DeliveryMode.PERSISTENT`` so messages survive broker
        restarts when the target queue is also durable.
        """
        channel = self._get_channel()

        if self._exchange_name:
            exchange = await channel.get_exchange(self._exchange_name)
        else:
            exchange = channel.default_exchange

        await exchange.publish(
            aio_pika.Message(
                body=body.encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers=headers,
            ),
            routing_key=routing_key,
        )
        logger.debug("Published to routing_key=%s", routing_key)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Return ``True`` if the connection is open and usable."""
        try:
            return (
                self._connection is not None
                and not self._connection.is_closed
                and self._channel is not None
                and not self._channel.is_closed
            )
        except Exception:
            return False
