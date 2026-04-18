import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("AgentLogger - AI Recommendation Agent")
logging.basicConfig(level=logging.INFO)


def main():
    logger.info("Hello, World!")
    logger.info("Initialized my first recommendation agent AI!")


if __name__ == "__main__":
    main()
