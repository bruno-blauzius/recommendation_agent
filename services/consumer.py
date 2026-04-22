import asyncio
import logging

from pydantic import ValidationError

from infraestructure.databases.redis import RedisDatabase
from infraestructure.mensageria.base import BrokerAdapter, BrokerMessage
from settings import _AGENT_DISPATCH_TIMEOUT
from schemas.message import AgentMessage, AgentType
from services.agent_recommendation_products import agent_recommendation_products
from services.agent_with_mcp import agent_with_mcp

logger = logging.getLogger(__name__)

# Idempotency key TTL: 24 h — long enough to prevent duplicate processing
# across restarts, short enough to self-clean.
_DEDUP_TTL_SECONDS = 86_400
_STATUS_TTL_SECONDS = 3_600


class MessageConsumer:
    """Async consumer loop that reads from a broker queue, deduplicates via
    Redis and dispatches each message to the correct agent pipeline.

    Design decisions:
    - ``asyncio.Semaphore(max_concurrency)`` caps parallel LLM calls,
      providing backpressure independent of the broker's prefetch_count.
    - Deduplication is SETNX-based: first worker to claim a message_id wins;
      duplicates are ack'd immediately (not re-processed).
    - On unrecoverable errors the message is nack'd with ``requeue=False``
      so it goes to the DLQ instead of looping forever.
    - ``stop()`` sets a shutdown event; the loop drains in-flight tasks
      before returning — enabling graceful shutdown on SIGTERM.

    Usage::

        consumer = MessageConsumer(
            broker=RabbitMQAdapter(...),
            redis=RedisDatabase(...),
            max_concurrency=10,
        )
        await consumer.start()
    """

    def __init__(
        self,
        broker: BrokerAdapter,
        redis: RedisDatabase,
        max_concurrency: int = 10,
    ) -> None:
        self._broker = broker
        self._redis = redis
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._shutdown_event = asyncio.Event()
        self._active_tasks: set[asyncio.Task] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect to broker + Redis and start the consume loop.

        Returns only after ``stop()`` is called and all in-flight tasks
        have finished.
        """
        logger.info("MessageConsumer starting")
        async with self._broker, self._redis:
            async for broker_msg in self._broker.consume():
                if self._shutdown_event.is_set():
                    logger.info("Shutdown signalled — stopping message loop")
                    break
                task = asyncio.create_task(self._handle(broker_msg))
                self._active_tasks.add(task)
                task.add_done_callback(self._active_tasks.discard)
                task.add_done_callback(self._log_task_exception)

            await self._drain()
        logger.info("MessageConsumer stopped")

    async def stop(self) -> None:
        """Signal the consume loop to stop after draining in-flight tasks."""
        logger.info("MessageConsumer stop requested")
        self._shutdown_event.set()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _log_task_exception(task: asyncio.Task) -> None:
        """Callback that surfaces unhandled exceptions from handler tasks."""
        if not task.cancelled() and not task.exception() is None:
            logger.error(
                "Unhandled exception in message handler task",
                exc_info=task.exception(),
            )

    async def _drain(self) -> None:
        """Wait for all in-flight tasks to complete."""
        if self._active_tasks:
            logger.info("Draining %d in-flight task(s)…", len(self._active_tasks))
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

    async def _handle(self, broker_msg: BrokerMessage) -> None:
        """Parse, deduplicate and dispatch a single broker message."""
        logger.info("Message received — broker_message_id=%s", broker_msg.message_id)
        # 1. Parse envelope
        try:
            msg = AgentMessage.model_validate_json(broker_msg.body)
        except ValidationError as exc:
            logger.error(
                "Invalid message payload — sending to DLQ. error=%s body=%.200s",
                exc,
                broker_msg.body,
            )
            await self._broker.nack(broker_msg, requeue=False)
            return

        # 2. Deduplication
        dedup_key = f"dedup:{msg.message_id}"
        is_new = await self._redis.set_if_not_exists(
            dedup_key, "1", ttl_seconds=_DEDUP_TTL_SECONDS
        )
        if not is_new:
            logger.info(
                "Duplicate message_id=%s correlation_id=%s — ack and skip",
                msg.message_id,
                msg.correlation_id,
            )
            await self._broker.ack(broker_msg)
            return

        logger.info(
            "Processing message_id=%s correlation_id=%s agent_type=%s",
            msg.message_id,
            msg.correlation_id,
            msg.agent_type,
        )
        # 3. Mark as processing
        await self._redis.set_status(
            msg.message_id, "processing", ttl_seconds=_STATUS_TTL_SECONDS
        )

        # 4. Dispatch under concurrency limit
        async with self._semaphore:
            await self._dispatch(msg, broker_msg)

    async def _dispatch(self, msg: AgentMessage, broker_msg: BrokerMessage) -> None:
        """Invoke the correct agent pipeline and ack/nack accordingly."""
        try:
            match msg.agent_type:
                case AgentType.DEFAULT:
                    await asyncio.wait_for(
                        agent_with_mcp(msg.prompt),
                        timeout=_AGENT_DISPATCH_TIMEOUT,
                    )
                case AgentType.RECOMMENDATION_PRODUCTS:
                    await asyncio.wait_for(
                        agent_recommendation_products(msg.prompt),
                        timeout=_AGENT_DISPATCH_TIMEOUT,
                    )
                case AgentType.CUSTOM:
                    raise NotImplementedError(
                        "Custom agent_type is not implemented yet"
                    )
                case _:
                    raise ValueError(f"Unknown agent_type: {msg.agent_type}")

            await self._redis.set_status(msg.message_id, "done")
            await self._broker.ack(broker_msg)
            logger.info(
                "Processed message_id=%s correlation_id=%s agent_type=%s",
                msg.message_id,
                msg.correlation_id,
                msg.agent_type,
            )

        except Exception as exc:
            logger.exception(
                "Failed to process message_id=%s correlation_id=%s: %s",
                msg.message_id,
                msg.correlation_id,
                exc,
            )
            await self._redis.set_status(msg.message_id, "failed")
            await self._broker.nack(broker_msg, requeue=False)
