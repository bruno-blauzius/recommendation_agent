from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class BrokerMessage:
    """Broker-agnostic envelope for a received message.

    Attributes:
        body:       Raw decoded message body (str).
        headers:    Optional metadata sent by the producer.
        message_id: Unique ID assigned by the broker (may differ from
                    the application-level ``AgentMessage.message_id``).
        raw:        Original broker-specific message object, kept for
                    ack/nack operations performed by the adapter.
    """

    def __init__(
        self,
        body: str,
        headers: dict[str, Any] | None = None,
        message_id: str | None = None,
        raw: Any = None,
    ) -> None:
        self.body = body
        self.headers: dict[str, Any] = headers or {}
        self.message_id = message_id
        self.raw = raw


class BrokerAdapter(ABC):
    """Abstract base for message-broker adapters (RabbitMQ, SQS, …).

    Concrete implementations must manage their own connection lifecycle
    and translate broker-specific APIs into the common interface below.
    This allows the consumer loop (``services/consumer.py``) to be
    completely broker-agnostic.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the broker."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close the connection and release resources."""

    async def __aenter__(self) -> "BrokerAdapter":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    # ------------------------------------------------------------------
    # Consuming
    # ------------------------------------------------------------------

    @abstractmethod
    def consume(self) -> AsyncIterator[BrokerMessage]:
        """Yield messages from the queue one at a time.

        Implementations should apply prefetch/QoS so that only
        *prefetch_count* messages are in-flight at once, providing
        natural backpressure for the consumer loop.

        Usage::

            async for msg in adapter.consume():
                await process(msg)
                await adapter.ack(msg)
        """

    @abstractmethod
    async def ack(self, message: BrokerMessage) -> None:
        """Acknowledge successful processing of *message*."""

    @abstractmethod
    async def nack(self, message: BrokerMessage, requeue: bool = True) -> None:
        """Reject *message*.

        Args:
            message: The message to reject.
            requeue: If ``True`` the broker re-enqueues the message for
                     another consumer.  Set to ``False`` to send it to a
                     dead-letter queue (DLQ).
        """

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    @abstractmethod
    async def publish(
        self,
        body: str,
        routing_key: str,
        headers: dict[str, Any] | None = None,
    ) -> None:
        """Publish *body* to the broker.

        Used to write results back to a response / reply queue.
        """

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @abstractmethod
    async def ping(self) -> bool:
        """Return ``True`` if the broker connection is healthy."""
