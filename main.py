import asyncio
import logging
import signal
import sys

from dotenv import load_dotenv

from infraestructure.databases.redis import RedisDatabase
from infraestructure.mensageria.rabbitmq import RabbitMQAdapter
from services.consumer import MessageConsumer

from settings import (
    _ENVIRONMENT,
    _RABBITMQ_DLX,
    _RABBITMQ_PREFETCH,
    _RABBITMQ_QUEUE,
    _RABBITMQ_URL,
    _REDIS_URL,
    _AGENT_MAX_CONCURRENCY,
)

load_dotenv()

logger = logging.getLogger("recommendation_agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def run_consumer() -> None:
    """Entry point for pub/sub consumer mode.

    Reads connection details from environment variables, builds the
    infrastructure adapters, and starts the consumer loop.  Signal
    handlers for SIGTERM and SIGINT request a graceful shutdown so
    in-flight messages are finished before the process exits.
    """
    rabbitmq_url = _RABBITMQ_URL
    queue_name = _RABBITMQ_QUEUE
    dead_letter_exchange = _RABBITMQ_DLX
    prefetch_count = _RABBITMQ_PREFETCH
    redis_url = _REDIS_URL
    max_concurrency = _AGENT_MAX_CONCURRENCY

    broker = RabbitMQAdapter(
        url=rabbitmq_url,
        queue_name=queue_name,
        prefetch_count=prefetch_count,
        dead_letter_exchange=dead_letter_exchange,
    )
    redis = RedisDatabase(url=redis_url)
    consumer = MessageConsumer(
        broker=broker,
        redis=redis,
        max_concurrency=max_concurrency,
    )

    loop = asyncio.get_running_loop()

    def _request_shutdown() -> None:
        logger.info("Shutdown signal received — draining in-flight messages…")
        loop.create_task(consumer.stop())

    # POSIX-only (Linux/macOS). Docker containers always run on Linux.
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _request_shutdown)

    logger.info(
        "Consumer starting (env=%s, queue=%s, concurrency=%d)",
        _ENVIRONMENT,
        queue_name,
        max_concurrency,
    )
    try:
        await consumer.start()
    except KeyboardInterrupt:
        # Windows fallback — Ctrl+C raises KeyboardInterrupt instead of SIGINT.
        logger.info("KeyboardInterrupt received — shutting down…")
        await consumer.stop()
    finally:
        logger.info("Consumer stopped.")


if __name__ == "__main__":
    asyncio.run(run_consumer())
