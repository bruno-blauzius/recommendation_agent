import asyncio
import logging
import os
import signal

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("recommendation_agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

_shutdown = asyncio.Event()


def _handle_signal(sig, frame):
    logger.info("Signal %s received — shutting down", sig)
    _shutdown.set()


async def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info(
        "Recommendation Agent starting (env=%s)", os.getenv("ENV", "development")
    )

    try:
        await _shutdown.wait()
    finally:
        logger.info("Recommendation Agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
